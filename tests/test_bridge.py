from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient

from partna_bridge.app import create_app
from partna_bridge.config import Settings
from partna_bridge.engine import EngineError
from partna_bridge.outbox import OutboxWorker


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail = False

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.fail:
            raise EngineError(502, "engine is unreachable")
        self.calls.append((path, payload))
        return {"ok": True, "path": path, "duplicate": False}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"ok": True}


@contextmanager
def bridge(tmp_path, **overrides: Any) -> Iterator[tuple[TestClient, FakeEngine, Any]]:
    values = {
        "engine_url": "https://engine.example",
        "engine_api_key": "secret-key",
        "public_url": "https://bridge.example",
        "brand": "ИИ Продавец",
        "destination_url": "https://shop.example/",
        "bridge_token": "bridge-token",
        "webhook_secret": "hook-secret",
        "allowed_origins": "",
        "outbox_db": str(tmp_path / "bridge.sqlite3"),
        "outbox_mode": "inline",
    }
    values.update(overrides)
    settings = Settings(**values)
    app = create_app(settings)
    with TestClient(app) as client:
        engine = FakeEngine()
        app.state.engine = engine
        yield client, engine, app


def test_health_never_echoes_the_key(tmp_path) -> None:
    with bridge(tmp_path) as (client, _, _):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["key_configured"] is True
    assert "secret-key" not in response.text


def test_redirect_sets_cookie_and_adds_ref(tmp_path) -> None:
    with bridge(tmp_path) as (client, _, _):
        response = client.get("/r/iron1", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://shop.example/?ref=IRON1"
    cookie = response.headers["set-cookie"]
    assert "pn_ref=IRON1" in cookie
    assert "HttpOnly" in cookie
    assert "Max-Age=2592000" in cookie


def test_redirect_rejects_bad_code(tmp_path) -> None:
    with bridge(tmp_path) as (client, _, _):
        response = client.get("/r/ab", follow_redirects=False)

    assert response.status_code == 400


def test_claim_uses_cookie_when_body_has_no_code(tmp_path) -> None:
    with bridge(tmp_path) as (client, engine, _):
        client.cookies.set("pn_ref", "IRON1")
        response = client.post("/v1/claim", json={"externalAccountId": "user-42"})

    assert response.status_code == 200
    assert engine.calls[0][0] == "/v1/referrals/claim"
    assert engine.calls[0][1]["code"] == "IRON1"


def test_claim_without_code_is_rejected(tmp_path) -> None:
    with bridge(tmp_path) as (client, engine, _):
        response = client.post("/v1/claim", json={"externalAccountId": "user-42"})

    assert response.status_code == 400
    assert engine.calls == []


def test_claim_falls_back_to_outbox_when_engine_is_down(tmp_path) -> None:
    with bridge(tmp_path) as (client, engine, app):
        engine.fail = True
        response = client.post(
            "/v1/claim",
            json={"code": "IRON1", "externalAccountId": "user-42"},
        )
        queued = _run(app.state.store.list_outbox())

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert queued[0]["path"] == "/v1/referrals/claim"


ORDER = {
    "eventId": "order:1",
    "occurredAt": "2026-11-19T12:00:00Z",
    "orderId": "1",
    "memberId": "user-42",
    "amount": 5_000_000,
    "currency": "RUB",
    "personalVolume": 0,
}


def test_order_requires_bridge_token(tmp_path) -> None:
    with bridge(tmp_path) as (client, engine, _):
        response = client.post("/v1/order", json=ORDER)

    assert response.status_code == 401
    assert engine.calls == []


def test_order_forwards_payload_inline(tmp_path) -> None:
    with bridge(tmp_path) as (client, engine, _):
        response = client.post(
            "/v1/order",
            json=ORDER,
            headers={"Authorization": "Bearer bridge-token"},
        )

    assert response.status_code == 200
    assert response.json()["queued"] is False
    path, payload = engine.calls[0]
    assert path == "/v1/orders"
    assert payload["eventId"] == "order:1"
    assert payload["memberId"] == "user-42"
    assert payload["amount"] == 5_000_000


def test_order_without_member_is_rejected_before_the_engine(tmp_path) -> None:
    payload = {key: value for key, value in ORDER.items() if key != "memberId"}

    with bridge(tmp_path) as (client, engine, _):
        response = client.post(
            "/v1/order",
            json=payload,
            headers={"Authorization": "Bearer bridge-token"},
        )

    assert response.status_code == 422
    assert engine.calls == []


def test_order_is_queued_in_queue_mode(tmp_path) -> None:
    with bridge(tmp_path, outbox_mode="queue") as (client, engine, app):
        response = client.post(
            "/v1/order",
            json=ORDER,
            headers={"Authorization": "Bearer bridge-token"},
        )
        assert response.status_code == 202
        assert engine.calls == []

        worker = OutboxWorker(app.state.store, engine)
        sent = _run(worker.run_once())
        rows = _run(app.state.store.list_outbox())

    assert sent == 1
    assert rows[0]["status"] == "sent"


def test_outbox_keeps_failed_entry_for_retry(tmp_path) -> None:
    with bridge(tmp_path, outbox_mode="queue") as (client, engine, app):
        engine.fail = True
        client.post(
            "/v1/order",
            json=ORDER,
            headers={"Authorization": "Bearer bridge-token"},
        )
        worker = OutboxWorker(app.state.store, engine)
        _run(worker.run_once())
        rows = _run(app.state.store.list_outbox())

    assert rows[0]["status"] == "pending"
    assert rows[0]["attempts"] == 1
    assert "unreachable" in rows[0]["last_error"]


def test_webhook_rejects_bad_signature(tmp_path) -> None:
    with bridge(tmp_path) as (client, _, _):
        response = client.post(
            "/webhooks/engine",
            content=b'{"eventId":"e1"}',
            headers={"X-Partner-Signature": "sha256=deadbeef"},
        )

    assert response.status_code == 401


def test_webhook_accepts_signature_and_reports_duplicate(tmp_path) -> None:
    body = json.dumps({"eventId": "e1", "type": "referral.claimed"}).encode()
    signature = hmac.new(b"hook-secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Partner-Signature": f"sha256={signature}", "Content-Type": "application/json"}

    with bridge(tmp_path) as (client, _, _):
        first = client.post("/webhooks/engine", content=body, headers=headers)
        second = client.post("/webhooks/engine", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json() == {"received": True, "duplicate": False}
    assert second.json() == {"received": True, "duplicate": True}


MEMBER = {
    "eventId": "member:user-42:iron",
    "occurredAt": "2026-11-19T12:00:00Z",
    "memberId": "user-42",
    "sponsorId": "iron",
    "placementId": "iron",
}


def test_member_is_forwarded_to_the_engine(tmp_path) -> None:
    with bridge(tmp_path) as (client, engine, _):
        response = client.post(
            "/v1/member",
            json=MEMBER,
            headers={"Authorization": "Bearer bridge-token"},
        )

    assert response.status_code == 200
    path, payload = engine.calls[0]
    assert path == "/v1/members"
    assert payload["sponsorId"] == "iron"


def test_member_requires_the_bridge_token(tmp_path) -> None:
    with bridge(tmp_path) as (client, engine, _):
        response = client.post("/v1/member", json=MEMBER)

    assert response.status_code == 401
    assert engine.calls == []


def test_server_claim_is_not_rate_limited(tmp_path) -> None:
    headers = {"Authorization": "Bearer bridge-token"}

    with bridge(tmp_path) as (client, engine, _):
        responses = [
            client.post(
                "/v1/claim",
                json={"code": "IRON1", "externalAccountId": f"user-{index}"},
                headers=headers,
            )
            for index in range(40)
        ]

    assert {response.status_code for response in responses} == {200}
    assert len(engine.calls) == 40


def test_browser_claim_is_rate_limited(tmp_path) -> None:
    with bridge(tmp_path) as (client, _, _):
        responses = [
            client.post(
                "/v1/claim",
                json={"code": "IRON1", "externalAccountId": f"user-{index}"},
            )
            for index in range(40)
        ]

    assert responses[29].status_code == 200
    assert responses[30].status_code == 429


def _run(coro):
    import asyncio

    return asyncio.run(coro)
