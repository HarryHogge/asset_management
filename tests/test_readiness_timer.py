"""The readiness timer (prompt 13): each day is recorded even when nobody
opens a page. Each test calls one pass directly, with a made-up clock and
made-up sources; no thread is started and nothing sleeps."""
import logging
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import app as dashboard
import fleet
import sharepoint
from fake_sharepoint import FakeClock, FakeSharePoint, FakeTokens, fake_env, make_item
from test_riga import history, lines, riga, uploaded, workbook, workbook_bytes  # noqa: F401

US_TZ = ZoneInfo('America/Los_Angeles')
DAY = datetime(2026, 3, 2, 9, 0, tzinfo=US_TZ)


@pytest.fixture(autouse=True)
def fresh_timer(monkeypatch):
    """Each test starts with no failure remembered, and with the CSV source."""
    monkeypatch.setattr(dashboard, '_timer_problems', {fleet.US: None, fleet.RIGA: None})
    monkeypatch.setattr(dashboard, 'SOURCE', dashboard.CsvSource(dashboard.ASSET_CSV,
                                                                 dashboard.SITE_TIMEZONE))


def us_lines(h):
    return [x for x in lines(h) if fleet.site_of(x) == fleet.US]


def timer_records(caplog):
    return [r for r in caplog.records if r.getMessage().startswith('Readiness timer')]


class GatedSharePoint(FakeSharePoint):
    """FakeSharePoint whose replies wait while its gate is cleared, so a test
    decides when a background refresh may finish."""

    def __init__(self, items):
        super().__init__(items)
        self.gate = threading.Event()
        self.gate.set()

    def get(self, url, headers=None, timeout=None):
        assert self.gate.wait(10), 'the test never let the refresh finish'
        return super().get(url, headers=headers, timeout=timeout)


class FailingSource:
    """A source whose load fails with whatever `error` is, until it is None."""

    def __init__(self, error):
        self.error = error
        self.good = dashboard.CsvSource(dashboard.ASSET_CSV, dashboard.SITE_TIMEZONE)

    def load(self):
        if self.error:
            raise self.error
        return self.good.load()


# --- The US line ---------------------------------------------------------------

def test_a_pass_with_no_page_visits_writes_todays_us_line(riga, history, caplog):
    caplog.set_level(logging.INFO)
    assert dashboard.readiness_pass(DAY) == [fleet.US]
    (line,) = us_lines(history)
    assert line['date'] == '2026-03-02' and line['source'].endswith('.csv')
    assert 'Readiness timer: recorded the US line for 2026-03-02.' in caplog.text


def test_sharepoint_gives_yesterdays_copy_first_then_todays(pfx, riga, history, monkeypatch):
    settings = sharepoint.load_settings(fake_env(pfx))
    fake = GatedSharePoint([make_item(100 + i, 'SN-TEST-%03d' % i) for i in range(3)])
    client = sharepoint.GraphClient(FakeTokens(), session=fake, sleep=lambda s: None)
    clock = FakeClock()
    source = sharepoint.SharePointSource(settings, 'America/Los_Angeles', client=client,
                                         clock=clock, background=True)
    source.load()                                       # the copy held since yesterday
    fake.gate.clear()                                   # the next refresh waits for the test
    source._data['loaded_at'] -= timedelta(days=1)
    clock.advance(settings['refresh_seconds'] + 1)      # a refresh is due
    monkeypatch.setattr(dashboard, 'SOURCE', source)
    now = datetime.now(US_TZ)
    assert dashboard.readiness_pass(now) == []          # yesterday's copy: not recorded
    fake.gate.set()
    with source._refresh_lock:                          # the background refresh has finished
        pass
    assert dashboard.readiness_pass(now) == [fleet.US]
    (line,) = us_lines(history)
    assert line['date'] == now.date().isoformat() and line['source'].startswith('SharePoint')


def test_a_second_pass_the_same_day_writes_and_logs_nothing(riga, history, caplog):
    dashboard.readiness_pass(DAY)
    caplog.clear()
    caplog.set_level(logging.DEBUG)
    assert dashboard.readiness_pass(DAY + timedelta(minutes=15)) == []
    assert len(us_lines(history)) == 1
    assert timer_records(caplog) == []


def test_a_failing_source_is_logged_once_per_cause_and_once_when_it_works(riga, history,
                                                                          monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    source = FailingSource(sharepoint.SourceError('the list could not be reached'))
    monkeypatch.setattr(dashboard, 'SOURCE', source)
    for i in range(4):
        assert dashboard.readiness_pass(DAY + timedelta(minutes=15 * i)) == []
    errors = [r for r in timer_records(caplog) if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert 'SourceError: the list could not be reached' in errors[0].getMessage()
    source.error = OSError('disk not ready')            # a new cause: logged again
    dashboard.readiness_pass(DAY + timedelta(hours=1))
    dashboard.readiness_pass(DAY + timedelta(hours=1, minutes=15))
    errors = [r for r in timer_records(caplog) if r.levelno == logging.ERROR]
    assert len(errors) == 2 and 'OSError: disk not ready' in errors[1].getMessage()
    source.error = None                                 # it recovers
    assert dashboard.readiness_pass(DAY + timedelta(hours=2)) == [fleet.US]
    dashboard.readiness_pass(DAY + timedelta(hours=2, minutes=15))
    again = [r for r in timer_records(caplog) if 'works again' in r.getMessage()]
    assert len(again) == 1 and again[0].levelno == logging.INFO
    assert len(us_lines(history)) == 1


def test_history_off_or_an_unavailable_source_does_nothing(riga, tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    off = fleet.ReadinessHistory(str(tmp_path / 'off' / 'h.jsonl'), off_reason='made-up reason')
    monkeypatch.setattr(dashboard, 'HISTORY', off)
    assert dashboard.readiness_pass(DAY) == []
    on = fleet.ReadinessHistory(str(tmp_path / 'on' / 'h.jsonl'))
    monkeypatch.setattr(dashboard, 'HISTORY', on)
    monkeypatch.setattr(dashboard, 'SOURCE', dashboard.UnavailableSource('SP_SITE_ID is missing.'))
    for _ in range(3):
        assert dashboard.readiness_pass(DAY) == []
    assert lines(off) == [] and lines(on) == []
    assert timer_records(caplog) == []


# --- Riga ------------------------------------------------------------------------

def test_a_pass_writes_rigas_line_from_a_good_workbook(uploaded, history, caplog):
    caplog.set_level(logging.INFO)
    assert dashboard.readiness_pass(DAY) == [fleet.US, fleet.RIGA]
    assert [fleet.site_of(x) for x in lines(history)] == [fleet.US, fleet.RIGA]
    assert 'Readiness timer: recorded the Riga line for ' in caplog.text
    assert dashboard.readiness_pass(DAY) == []


def test_with_no_riga_workbook_the_us_line_is_still_written(riga, history, caplog):
    caplog.set_level(logging.DEBUG)
    assert dashboard.readiness_pass(DAY) == [fleet.US]
    assert [fleet.site_of(x) for x in lines(history)] == [fleet.US]
    assert not [r for r in timer_records(caplog) if r.levelno >= logging.WARNING]


# --- The thread ------------------------------------------------------------------

def test_importing_app_starts_no_timer_thread():
    names = [t.name for t in threading.enumerate()]
    assert dashboard.TIMER_THREAD_NAME not in names


def test_the_loop_keeps_going_after_an_unexpected_error(monkeypatch, caplog):
    calls, sleeps = [], []

    def bad_pass():
        calls.append(1)
        raise RuntimeError('made-up bug')

    class Stop(Exception):
        pass

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 3:
            raise Stop

    monkeypatch.setattr(dashboard, 'readiness_pass', bad_pass)
    with pytest.raises(Stop):
        dashboard._timer_loop(sleep=sleep)
    assert sleeps == [60, 900, 900, 900] and len(calls) == 3
    assert caplog.text.count('Readiness timer: unexpected error in a pass') == 3


# --- The trend -------------------------------------------------------------------

def test_seven_daily_passes_give_seven_points_in_a_row(riga, history):
    for i in range(7):
        assert dashboard.readiness_pass(DAY + timedelta(days=i)) == [fleet.US]
    t = fleet.trend(history.entries(fleet.US), (DAY + timedelta(days=6)).date())
    assert t['points'] == 7
    assert None not in t['series']['Overall']
