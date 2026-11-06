import os

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def database_url():
    url = os.getenv("PLATFORM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PLATFORM_TEST_DATABASE_URL to a dedicated migrated test database")
    if not url.split("?", 1)[0].endswith("/platform_test"):
        pytest.fail("Integration tests require a database named platform_test")
    return url
