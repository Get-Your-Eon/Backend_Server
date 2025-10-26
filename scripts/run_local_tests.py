# Minimal local test harness that calls the FastAPI app endpoints with mocked
# dependencies (no code changes). It mocks DB and Redis to exercise the
# database-path logic and avoid external API calls.

import asyncio
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
# The application has a pathological use of `Query` for a path parameter which
# raises an AssertionError during FastAPI route construction on import. To run
# local tests without changing application code, monkeypatch FastAPI's params
# so that `Query` is treated like `Path` during import only.
try:
    import fastapi.params as _params
    # preserve original for safety
    _original_Query = getattr(_params, 'Query', None)
    _params.Query = getattr(_params, 'Path')
except Exception:
    _original_Query = None
from types import SimpleNamespace

# Import the app
from app.main import app

# --- Mocks ---
class DummyResult:
    def __init__(self, rows):
        self._rows = rows
    def fetchall(self):
        return self._rows
    def fetchone(self):
        return self._rows[0] if self._rows else None

class DummyRow:
    def __init__(self, mapping):
        self._mapping = mapping

class FakeDBSession:
    def __init__(self):
        # Prepare fake data keyed by query type
        self.station_rows = [
            DummyRow({
                'station_id': '5778',
                'addr': '경기도 성남시 분당구 분당로 50 (수내동, 분당구청) 실외주차장',
                'station_name': '분당구청 충전소',
                'lat': '37.374109692',
                'lon': '127.130205155'
            })
        ]
        self.charger_rows = [
            DummyRow({'cp_id': '12696', 'cp_nm': '급속01', 'cp_stat': '1', 'charge_tp': '2'}),
            DummyRow({'cp_id': '12697', 'cp_nm': '급속02', 'cp_stat': '1', 'charge_tp': '2'})
        ]

    async def execute(self, sql, params=None):
        text = str(sql).lower()
        # crude detection
        if 'from stations' in text and 'where cs_id' in text:
            return DummyResult(self.station_rows)
        if 'from stations' in text:
            return DummyResult(self.station_rows)
        if 'from chargers' in text:
            return DummyResult(self.charger_rows)
        # default
        return DummyResult([])

    async def commit(self):
        return None

    async def rollback(self):
        return None

class FakeRedis:
    def __init__(self):
        self.store = {}
    async def get(self, key):
        return None
    async def setex(self, key, expire, value):
        self.store[key] = value
        return True

# Fake dependency providers
async def fake_get_async_session():
    return FakeDBSession()

async def fake_get_redis_client():
    return FakeRedis()

# Fake API key dependency (accept any)
async def fake_frontend_api_key_required():
    return "ok"

# Apply dependency overrides
app.dependency_overrides = getattr(app, 'dependency_overrides', {})
from app.main import frontend_api_key_required, get_async_session, get_redis_client
app.dependency_overrides[frontend_api_key_required] = fake_frontend_api_key_required
app.dependency_overrides[get_async_session] = fake_get_async_session
app.dependency_overrides[get_redis_client] = fake_get_redis_client

client = TestClient(app)


def test_stations():
    print('\n=== TEST: /api/v1/stations (DB path) ===')
    params = {
        'lat': '37.374109692',
        'lon': '127.130205155',
        'radius': '700'
    }
    resp = client.get('/api/v1/stations', params=params, headers={'api_key': 'test'})
    print('status_code:', resp.status_code)
    try:
        print('response:', json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception as e:
        print('response text:', resp.text)


def test_station_chargers():
    print('\n=== TEST: /api/v1/station/{id}/chargers (DB path) ===')
    params = {
        'addr': '경기도 성남시 분당구 분당로 50 (수내동, 분당구청) 실외주차장'
    }
    resp = client.get('/api/v1/station/5778/chargers', params=params, headers={'api_key': 'test'})
    print('status_code:', resp.status_code)
    try:
        print('response:', json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception as e:
        print('response text:', resp.text)


if __name__ == '__main__':
    test_stations()
    test_station_chargers()

# restore original Query if we changed it
try:
    if _original_Query is not None:
        import fastapi.params as _params2
        _params2.Query = _original_Query
except Exception:
    pass
