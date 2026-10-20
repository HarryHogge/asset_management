import os

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
