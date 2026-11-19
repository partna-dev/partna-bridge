from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Fact(BaseModel):
    """A fact the host reports; field names follow the engine contract."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    event_id: str = Field(alias="eventId", min_length=1, max_length=200)
    occurred_at: datetime = Field(alias="occurredAt")


class OrderFact(_Fact):
    order_id: str = Field(alias="orderId", min_length=1, max_length=64)
    member_id: str = Field(alias="memberId", min_length=1, max_length=64)
    amount: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    personal_volume: Decimal = Field(alias="personalVolume", ge=0)
    product_id: str | None = Field(default=None, alias="productId", max_length=64)
    event_at: datetime | None = Field(default=None, alias="eventAt")
    retail_amount: int | None = Field(default=None, alias="retailAmount", ge=0)
    certificate_amount: int | None = Field(default=None, alias="certificateAmount", ge=0)


class RefundFact(_Fact):
    refund_id: str = Field(alias="refundId", min_length=1, max_length=64)
    order_id: str = Field(alias="orderId", min_length=1, max_length=64)
    member_id: str | None = Field(default=None, alias="memberId", max_length=64)
    amount: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)


class MemberFact(_Fact):
    member_id: str = Field(alias="memberId", min_length=1, max_length=64)
    sponsor_id: str | None = Field(default=None, alias="sponsorId", max_length=64)
    placement_id: str | None = Field(default=None, alias="placementId", max_length=64)
    leg: Literal["left", "right"] | None = None
    status: Literal["active", "inactive"] = "active"


class ClaimRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str = ""
    external_account_id: str = Field(alias="externalAccountId", min_length=1, max_length=64)


class PartnerLinkRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    external_account_id: str = Field(alias="externalAccountId", min_length=1, max_length=64)
    destination_url: str | None = Field(default=None, alias="destinationUrl")
