from redis.exceptions import ConnectionError

from services.api import cache
from services.api.db import Village


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.ttls = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, *, ex):
        self.values[key] = value
        self.ttls.append(ex)


def test_directory_cache_and_browser_revalidation(setup, monkeypatch):
    client, factory, headers = setup
    redis = MemoryRedis()
    monkeypatch.setattr(cache.settings, 'redis_url', 'redis://test')
    monkeypatch.setattr(cache, 'redis_client', lambda _: redis)
    path = '/api/v1/villages?q=TEST'
    first = client.get(path, headers=headers['a'])
    assert first.status_code == 200
    assert first.headers['cache-control'] == 'private, no-cache'
    assert 'Authorization' in first.headers['vary']
    assert redis.ttls == [cache.settings.redis_directory_ttl_seconds]

    with factory() as db:
        db.add(Village(id='TEST-C', name='TEST added', district='Test', taluka='Test', jurisdiction='scope-a', provenance={}))
        db.commit()
    validator = {'If-None-Match': 'W/'+first.headers['etag']}
    assert client.get(path, headers=validator).status_code == 401
    unchanged = client.get(path, headers={**headers['a'], **validator})
    assert unchanged.status_code == 304 and unchanged.content == b''
    assert len(redis.ttls) == 1
    assert client.get(path+'&limit=1', headers=headers['a']).json() != first.json()

    redis.values.clear()
    refreshed = client.get(path, headers={**headers['a'], **validator})
    assert refreshed.status_code == 200 and refreshed.headers['etag'] != first.headers['etag']
    assert len(refreshed.json()) == len(first.json())+1


def test_redis_failure_preserves_directory_reads_and_sensitive_responses(setup, monkeypatch):
    client, _, headers = setup
    monkeypatch.setattr(cache.settings, 'redis_url', 'redis://test')

    class OfflineRedis:
        def get(self, key):
            raise ConnectionError('Test connection failure')

    monkeypatch.setattr(cache, 'redis_client', lambda _: OfflineRedis())
    directory = client.get('/api/v1/villages', headers=headers['a'])
    assert directory.status_code == 200 and len(directory.json()) == 2
    for path in ('/api/v1/me', '/api/v1/admin/complaints', '/api/v1/villages/TEST-A/supply-outlook'):
        response = client.get(path, headers=headers['a'])
        assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
        assert 'etag' not in response.headers


def test_scoped_prediction_request_does_not_reuse_statewide_cache(setup, monkeypatch):
    client, factory, headers = setup
    redis = MemoryRedis()
    monkeypatch.setattr(cache.settings, 'redis_url', 'redis://test')
    monkeypatch.setattr(cache, 'redis_client', lambda _: redis)
    path = '/api/v1/supply-predictions'
    statewide = client.get(path, headers=headers['s'])
    assert statewide.json()['total'] == 2 and len(redis.ttls) == 1
    scoped = client.get(path, headers={**headers['a'], 'If-None-Match': statewide.headers['etag']})
    assert scoped.status_code == 200 and scoped.json()['total'] == 1
    assert scoped.json()['rows'][0]['id'] == 'TEST-A'
    with factory() as db:
        db.get(Village, 'TEST-A').jurisdiction = 'scope-b'
        db.commit()
    after = client.get(path, headers={**headers['a'], 'If-None-Match': scoped.headers['etag']})
    assert after.status_code == 200 and after.json()['total'] == 0
    assert len(redis.ttls) == 1
