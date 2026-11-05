"""Unit and Integration Tests for API Response Caching Layer."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.cache.response_cache import (
    RESPONSE_CACHE_SERVICE,
    cache_response,
    invalidate_response_cache,
)


def _make_mock_request(
    path: str = "/api/v1/test",
    method: str = "GET",
    query_params: dict | None = None,
    headers: dict | None = None,
) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()],
    }
    req = Request(scope)
    # mock query_params
    req._query_params = query_params or {}
    return req


def test_normalize_query_hash():
    # Order independence
    h1 = RESPONSE_CACHE_SERVICE.normalize_query_hash({"b": "2", "a": "1"})
    h2 = RESPONSE_CACHE_SERVICE.normalize_query_hash({"a": "1", "b": "2"})
    assert h1 == h2
    assert len(h1) == 16

    # Empty query
    assert RESPONSE_CACHE_SERVICE.normalize_query_hash({}) == "none"
    assert RESPONSE_CACHE_SERVICE.normalize_query_hash({"a": ""}) == "none"


def test_resolve_locale():
    # Query param takes precedence
    req1 = _make_mock_request(query_params={"lang": "km"}, headers={"accept-language": "en"})
    assert RESPONSE_CACHE_SERVICE.resolve_locale(req1) == "km"

    # X-Locale header
    req2 = _make_mock_request(headers={"x-locale": "cn"})
    assert RESPONSE_CACHE_SERVICE.resolve_locale(req2) == "cn"

    # Accept-Language mapping
    req3 = _make_mock_request(headers={"accept-language": "zh-CN,zh;q=0.9"})
    assert RESPONSE_CACHE_SERVICE.resolve_locale(req3) == "cn"

    req4 = _make_mock_request(headers={"accept-language": "ja"})
    assert RESPONSE_CACHE_SERVICE.resolve_locale(req4) == "jp"

    # Default fallback
    req5 = _make_mock_request()
    assert RESPONSE_CACHE_SERVICE.resolve_locale(req5) == "default"


def test_build_cache_key():
    key = RESPONSE_CACHE_SERVICE.build_cache_key(
        namespace="translations",
        method="GET",
        path="/api/admin/v1/translations",
        query_hash="abc12345",
        locale="km",
    )
    assert ":resp:translations:GET:api_admin_v1_translations:abc12345:km" in key


@pytest.mark.asyncio
async def test_set_and_get_cached_response():
    key = "clothing_store:resp:test:GET:test:123:en"
    content = json.dumps({"message": "hello world"})

    await RESPONSE_CACHE_SERVICE.set_cached_response(
        key=key,
        content=content,
        status_code=200,
        ttl=60,
    )

    cached = await RESPONSE_CACHE_SERVICE.get_cached_response(key)
    assert cached is not None
    assert cached["content"] == content
    assert cached["status_code"] == 200

    # Invalidate namespace
    evicted = await RESPONSE_CACHE_SERVICE.invalidate_namespace("test")
    assert evicted >= 1

    cleared = await RESPONSE_CACHE_SERVICE.get_cached_response(key)
    assert cleared is None


@pytest.mark.asyncio
async def test_cache_response_decorator_hit_and_miss():
    call_count = 0

    @cache_response(ttl=60, namespace="test_dec", include_locale=True)
    async def sample_endpoint(request: Request):
        nonlocal call_count
        call_count += 1
        return {"count": call_count, "data": "success"}

    req = _make_mock_request(path="/api/v1/sample", query_params={"category": "shirts"})

    # Clear before run
    await invalidate_response_cache("test_dec")

    # 1. First call -> MISS
    res1 = await sample_endpoint(request=req)
    assert res1.headers.get("X-Cache") == "MISS"
    data1 = json.loads(res1.body.decode("utf-8"))
    assert data1["count"] == 1

    # 2. Second call -> HIT (handler function should NOT be re-executed)
    res2 = await sample_endpoint(request=req)
    assert res2.headers.get("X-Cache") == "HIT"
    data2 = json.loads(res2.body.decode("utf-8"))
    assert data2["count"] == 1
    assert call_count == 1  # Function was called only once!

    # 3. Third call with different query param -> MISS
    req_diff = _make_mock_request(path="/api/v1/sample", query_params={"category": "pants"})
    res3 = await sample_endpoint(request=req_diff)
    assert res3.headers.get("X-Cache") == "MISS"
    data3 = json.loads(res3.body.decode("utf-8"))
    assert data3["count"] == 2
    assert call_count == 2

