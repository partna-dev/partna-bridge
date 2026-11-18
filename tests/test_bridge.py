from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi.testclient import TestClient

from partna_bridge.app import create_app
from partna_bridge.config import Settings


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, payload))
        return {"ok": True, "path": path, "duplicate": False}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"ok": True}


def make_client(**overrides: Any) -> tuple[TestClient, FakeEngine]:
    settings = Settings(
        engine_url="https://engine.example",
        engine_api_key="secret-key",
        public_url="https://bridge.example",
        brand="ИИ Продавец",
        destination_url="https://shop.example/",
        bridge_token="bridge-token",
        webhook_secret="hook-secret",
        allowed_origins="",
        **overrides,
    )
    app = create_app(settings)
    engine = FakeEngine()
    app.state.engine = engine
    return TestClient(app), engine


def test_health_never_echoes_the_key() -> None:
    client, _ = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["key_configured"] is True
    assert "secret-key" not in response.text


def test_redirect_sets_cookie_and_adds_ref() -> None:
    client, _ = make_client()

    response = client.get("/r/iron1", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://shop.example/?ref=IRON1"
    cookie = response.headers["set-cookie"]
    assert "pn_ref=IRON1" in cookie
    assert "HttpOnly" in cookie
    assert "Max-Age=2592000" in cookie


def test_redirect_rejects_bad_code() -> None:
    client, _ = make_client()

    response = client.get("/r/ab", follow_redirects=False)

    assert response.status_code == 400


def test_claim_uses_cookie_when_body_has_no_code() -> None:
    client, engine = make_client()
    client.cookies.set("pn_ref", "IRON1")

    response = client.post("/v1/claim", json={"externalAccountId": "user-42"})

    assert response.status_code == 200
    assert engine.calls[0][0] == "/v1/referrals/claim"
    assert engine.calls[0][1]["code"] == "IRON1"


def test_claim_without_code_is_rejected() -> None:
    client, engine = make_client()

    response = client.post("/v1/claim", json={"externalAccountId": "user-42"})

    assert response.status_code == 400
    assert engine.calls == []


def test_order_requires_bridge_token() -> None:
    client, engine = make_client()

    response = client.post("/v1/order", json={"orderId": "1"})

    assert response.status_code == 401
    assert engine.calls == []


def test_order_forwards_payload_with_token() -> None:
    client, engine = make_client()

    response = client.post(
        "/v1/order",
        json={"eventId": "order:1", "orderId": "1", "amount": 5_000_000},
        headers={"Authorization": "Bearer bridge-token"},
    )

    assert response.status_code == 200
    assert engine.calls[0][0] == "/v1/orders"
    assert engine.calls[0][1]["amount"] == 5_000_000


def test_webhook_rejects_bad_signature() -> None:
    client, _ = make_client()

    response = client.post(
        "/webhooks/engine",
        content=b'{"eventId":"e1"}',
        headers={"X-Partner-Signature": "sha256=deadbeef"},
    )

    assert response.status_code == 401


def test_webhook_accepts_signature_and_reports_duplicate() -> None:
    client, _ = make_client()
    body = json.dumps({"eventId": "e1", "type": "referral.claimed"}).encode()
    signature = hmac.new(b"hook-secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Partner-Signature": f"sha256={signature}", "Content-Type": "application/json"}

    first = client.post("/webhooks/engine", content=body, headers=headers)
    second = client.post("/webhooks/engine", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json() == {"received": True, "duplicate": False}
    assert second.json() == {"received": True, "duplicate": True}
