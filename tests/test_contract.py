from __future__ import annotations

import json
from pathlib import Path

from partna_bridge.contract import FACTS_OPERATIONS, ClaimResponse, FactResponse, LinkResponse
from partna_bridge.schemas import (
    ClaimRequest,
    MemberFact,
    OrderFact,
    PartnerLinkRequest,
    RefundFact,
)
from partna_bridge.spec import TARGET, render

EXAMPLES = Path(__file__).resolve().parents[1] / "spec" / "examples"

REQUESTS = {
    "claim.json": ClaimRequest,
    "partner-link.json": PartnerLinkRequest,
    "order.json": OrderFact,
    "refund.json": RefundFact,
    "member.json": MemberFact,
}


def _example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_the_snapshot_matches_the_app() -> None:
    assert TARGET.is_file(), "spec/partna-facts.v1.json is missing"
    assert TARGET.read_text(encoding="utf-8") == render(), (
        "contract is out of date: run uv run python scripts/export_spec.py"
    )


def test_the_contract_holds_only_the_public_operations() -> None:
    spec = json.loads(TARGET.read_text(encoding="utf-8"))

    assert sorted(spec["paths"]) == sorted(path for _, path in FACTS_OPERATIONS)
    for path, operations in spec["paths"].items():
        assert list(operations) == ["post"], path


def test_examples_fit_the_requests() -> None:
    for name, model in REQUESTS.items():
        model.model_validate(_example(name))


def test_responses_fit_the_declared_models() -> None:
    order = _example("order.json")
    fact = FactResponse.model_validate(
        {
            "queued": False,
            "eventId": order["eventId"],
            "engine": {"eventId": order["eventId"], "status": "accepted", "duplicate": False},
        }
    )
    assert fact.engine is not None and fact.engine.status == "accepted"

    pending = json.loads(
        json.dumps(
            {
                "queued": False,
                "eventId": "order:order-1",
                "engine": {
                    "eventId": "order:order-1",
                    "status": "pending_member",
                    "duplicate": False,
                },
                "extraFromEngine": {"kept": True},
            }
        )
    )
    kept = FactResponse.model_validate(pending)
    assert kept.model_extra and kept.model_extra["extraFromEngine"] == {"kept": True}

    claim = ClaimResponse.model_validate(
        {
            "status": "claimed",
            "code": "IRON",
            "sponsorId": "user-7",
            "memberId": "user-42",
            "claimedAt": "2026-11-01T10:00:00Z",
        }
    )
    assert claim.memberId == "user-42"

    queued_claim = ClaimResponse.model_validate(
        {"status": "pending", "eventId": "claim:IRON:user-42"}
    )
    assert queued_claim.eventId and queued_claim.memberId is None

    link = LinkResponse.model_validate(
        {"code": "IRON", "url": "https://shop.example/r/IRON", "expiresAt": None}
    )
    assert link.code == "IRON"
