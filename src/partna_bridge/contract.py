"""Публичная форма ответов моста.

Это контракт для клиентов и MCP: поля описаны здесь, отсюда же собирается
OpenAPI в `spec/partna-facts.v1.json`. Всё, что пришло от ядра сверх модели,
сохраняется: контракт расширяемый, ломать чужие поля нельзя.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _OpenModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class IngestResult(_OpenModel):
    eventId: str
    status: str
    duplicate: bool


class FactResponse(_OpenModel):
    """Ответ на заказ, возврат или участника."""

    queued: bool
    eventId: str
    engine: IngestResult | None = None


class ClaimResponse(_OpenModel):
    """Привязка клиента к коду партнёра: сразу или через очередь."""

    status: str
    code: str | None = None
    sponsorId: str | None = None
    memberId: str | None = None
    claimedAt: datetime | None = None
    eventId: str | None = None


class LinkResponse(_OpenModel):
    code: str
    url: str
    expiresAt: datetime | None = None


class ErrorResponse(_OpenModel):
    detail: str


FACTS_OPERATIONS: tuple[tuple[str, str], ...] = (
    ("post", "/v1/claim"),
    ("post", "/v1/partner-link"),
    ("post", "/v1/order"),
    ("post", "/v1/refund"),
    ("post", "/v1/member"),
)
