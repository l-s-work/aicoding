"""
main.py 入口与全局异常处理回归测试

覆盖重点：
- 根路由与健康检查
- 自定义 422 参数校验错误格式
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_root_and_health_routes_should_work_without_lifespan() -> None:
    # 关闭 lifespan，避免测试中执行真实 init_db/seed 流程。
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "docs" in root_resp.json()

        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_validation_error_handler_should_return_custom_422_payload() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # page 最小值为 1，传 0 触发 RequestValidationError
        resp = await client.get("/api/products", params={"page": 0})

    assert resp.status_code == 422
    payload = resp.json()
    assert payload["detail"] == "请求参数验证失败"
    assert isinstance(payload["errors"], list)
    assert len(payload["errors"]) >= 1
