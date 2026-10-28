"""Pills in the light theme: readable text, and visible against the page."""
import os
import re

import pytest

import app as dashboard
import assets as asset_data

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = sorted(set(asset_data.FONT_COLORS.values()) | {'#ffffff'})


def read(name):
    with open(os.path.join(REPO, 'templates', name), encoding='utf-8') as f:
        return f.read()


def meets_both_rules(pill):
    text = asset_data.contrast(pill['fg'], pill['bg'])
    edge = pill['bg'] if pill['border'] == 'transparent' else pill['border']
    return text >= 4.5 and all(asset_data.contrast(edge, page) >= 3.0
                               for page in asset_data.LIGHT_BACKGROUNDS)


@pytest.mark.parametrize('name', sorted(asset_data.BG_COLORS))
def test_every_list_color_is_readable_in_the_light_theme(name):
    bg = asset_data.BG_COLORS[name]
    for fg in FONTS:
        assert meets_both_rules(asset_data.light_pill(bg, fg)), (name, fg)


def test_pills_that_already_pass_are_left_alone():
    # Dark blue with white text passes both rules as it is.
    assert asset_data.light_pill('#004e8c', '#ffffff') == {
        'bg': '#004e8c', 'fg': '#ffffff', 'border': 'transparent'}


def test_pale_pills_keep_their_fill_and_get_a_border():
    pill = asset_data.light_pill('#dcf5f9', '#005b70')
    assert pill['bg'] == '#dcf5f9' and pill['border'] != 'transparent'


def test_page_backgrounds_match_the_light_theme():
    base = read('base.html')
    light = base.split('[data-theme="light"] {', 1)[1].split('}', 1)[0]
    for var in ('--bg', '--surface', '--surface-2', '--row-hover'):
        value = re.search(var + r':\s*(#[0-9A-Fa-f]{6})', light).group(1).lower()
        assert value in asset_data.LIGHT_BACKGROUNDS, var


def test_dark_theme_keeps_the_list_colors_exactly():
    with dashboard.app.app_context():
        macros = dashboard.app.jinja_env.get_template('_macros.html').module
        fields = {'status': {'colors': {'RMA': {'bg': '#fde7e9', 'fg': '#a4262c'}}}}
        html = str(macros.pill(fields, 'status', 'RMA'))
    # The same inline colors as before; the light ones ride along as variables.
    assert 'style="background: #fde7e9; color: #a4262c; --light-bg:' in html
    # Only a light-theme rule reads those variables.
    for line in read('base.html').splitlines():
        if '.pill.listed' in line:
            assert line.strip().startswith('[data-theme="light"]'), line


def light_var(name):
    light = read('base.html').split('[data-theme="light"] {', 1)[1].split('}', 1)[0]
    return re.search(name + r':\s*(#[0-9A-Fa-f]{6})', light).group(1)


@pytest.mark.parametrize('var, text', [
    ('--good', '#ffffff'), ('--warn', '#000000'), ('--bad', '#ffffff'), ('--lost', '#ffffff')])
def test_condition_pills_meet_the_same_rules_in_the_light_theme(var, text):
    fill = light_var(var)
    assert meets_both_rules({'bg': fill, 'fg': text, 'border': 'transparent'}), var
    if var == '--warn':
        assert '[data-theme="light"] .pill.cond.limited { color: #000000; }' in read('overview.html')


def test_no_condition_pill_border_stands_out_in_the_light_theme():
    border = light_var('--muted')
    assert all(asset_data.contrast(border, page) >= 3.0 for page in asset_data.LIGHT_BACKGROUNDS)
    # Its fill is clear, so its text sits on the page itself.
    assert all(asset_data.contrast(light_var('--text-2'), page) >= 4.5
               for page in asset_data.LIGHT_BACKGROUNDS)
