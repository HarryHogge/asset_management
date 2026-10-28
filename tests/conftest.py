import atexit
import os
import shutil
import tempfile

# Every page load may add a line to the readiness history. Keep that file out
# of the repo folder: point READINESS_HISTORY at a temporary folder before the
# app is imported. Tests of the history itself use their own tmp_path.
_history_dir = tempfile.mkdtemp(prefix='asset-tests-')
atexit.register(shutil.rmtree, _history_dir, ignore_errors=True)
os.environ['READINESS_HISTORY'] = os.path.join(_history_dir, 'readiness_history.jsonl')

# The app reads ASSET_SOURCE when it is imported. Tests always start from the
# CSV source and swap in a fake SharePoint source where they need one, so a
# developer's own .env cannot change what the tests do. load_dotenv() never
# overrides a variable that is already set.
os.environ['ASSET_SOURCE'] = 'csv'
os.environ['SITE_TIMEZONE'] = 'America/Los_Angeles'
for name in list(os.environ):
    if name.startswith('SP_'):
        del os.environ[name]

import pytest  # noqa: E402

from fake_sharepoint import make_pfx  # noqa: E402


@pytest.fixture(scope='session')
def pfx(tmp_path_factory):
    """A made-up certificate, written to a temporary folder outside the repo."""
    path = tmp_path_factory.mktemp('cert') / 'test-cert.pfx'
    path.write_bytes(make_pfx('correct horse battery'))
    return {'path': str(path), 'password': 'correct horse battery'}
