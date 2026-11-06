import pytest

from config.sentry import init_sentry, scrub_event

_DSN = 'https://public@o1.ingest.sentry.io/42'


def test_init_is_inert_without_dsn(monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    calls = []
    monkeypatch.setattr('sentry_sdk.init', lambda **kwargs: calls.append(kwargs))

    assert init_sentry() is False
    assert calls == []


def test_init_uses_safe_options(monkeypatch):
    calls = []
    monkeypatch.setattr('sentry_sdk.init', lambda **kwargs: calls.append(kwargs))
    monkeypatch.setenv('SENTRY_ENVIRONMENT', 'test')
    monkeypatch.setenv('SENTRY_TRACES_SAMPLE_RATE', '0.25')

    assert init_sentry(_DSN) is True

    (options,) = calls
    assert options['dsn'] == _DSN
    assert options['environment'] == 'test'
    assert options['traces_sample_rate'] == 0.25
    assert options['send_default_pii'] is False
    assert options['max_request_body_size'] == 'never'
    assert options['before_send'] is scrub_event
    assert [type(integration).__name__ for integration in options['integrations']] == [
        'DjangoIntegration'
    ]


def test_init_rejects_insecure_dsn(monkeypatch):
    monkeypatch.setattr('sentry_sdk.init', lambda **kwargs: pytest.fail('init must not run'))

    with pytest.raises(ValueError):
        init_sentry('http://public@o1.ingest.sentry.io/42')


@pytest.mark.parametrize('rate', ['-0.1', '1.1', 'not-a-number'])
def test_init_rejects_invalid_sample_rate(monkeypatch, rate):
    monkeypatch.setattr('sentry_sdk.init', lambda **kwargs: pytest.fail('init must not run'))
    monkeypatch.setenv('SENTRY_TRACES_SAMPLE_RATE', rate)

    with pytest.raises(ValueError):
        init_sentry(_DSN)


def test_scrub_event_removes_credentials_and_payloads():
    event = {
        'request': {
            'headers': {
                'Authorization': 'Bearer super-secret',
                'Cookie': 'session=super-secret',
                'X-Api-Key': 'super-secret',
                'Accept': 'application/json',
            },
            'cookies': {'session': 'super-secret'},
            'data': {'password': 'super-secret'},
            'query_string': 'api_key=super-secret',
        },
        'contexts': {'request': {'token': 'super-secret', 'safe': 'hello'}},
        'extra': {'password': 'super-secret', 'safe': 'hello'},
        'tags': {'api-key': 'super-secret'},
        'breadcrumbs': {
            'values': [
                {'message': 'Authorization: Bearer super-secret'},
                {'data': {'secret': 'super-secret', 'safe': 'hello'}},
            ]
        },
    }

    scrubbed = scrub_event(event, {})

    assert 'super-secret' not in repr(scrubbed)
    request = scrubbed['request']
    assert request['headers']['Authorization'] == '[REDACTED]'
    assert request['headers']['Cookie'] == '[REDACTED]'
    assert request['headers']['X-Api-Key'] == '[REDACTED]'
    assert request['headers']['Accept'] == 'application/json'
    assert 'cookies' not in request
    assert 'data' not in request
    assert 'query_string' not in request
    assert scrubbed['extra'] == {'password': '[REDACTED]', 'safe': 'hello'}
    assert scrubbed['contexts']['request'] == {'token': '[REDACTED]', 'safe': 'hello'}
    assert scrubbed['tags'] == {'api-key': '[REDACTED]'}
    assert scrubbed['breadcrumbs']['values'] == [
        {'message': 'Authorization: Bearer [REDACTED]'},
        {'data': {'secret': '[REDACTED]', 'safe': 'hello'}},
    ]


def test_scrub_event_tolerates_missing_request():
    assert scrub_event({'message': 'boom'}, {}) == {'message': 'boom'}
