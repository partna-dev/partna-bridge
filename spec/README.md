# Facts contract, version 1

English · [Русский](README.ru.md)

Five operations that make up every write into a partner programme. Everything else
is reading (the cabinet) and settings (the owner's cabinet); they are not part of
this contract.

- `POST /v1/claim` — bind a client to a partner code;
- `POST /v1/member` — a programme member and who invited them;
- `POST /v1/order` — a client paid;
- `POST /v1/refund` — a client was refunded;
- `POST /v1/partner-link` — a partner's link for their clients.

Schema: [`partna-facts.v1.json`](partna-facts.v1.json) — OpenAPI 3.1. Request
examples: [`examples/`](examples).

## Authorisation

`POST /v1/claim` takes the partner code and needs no token: it is called by the
browser during signup or by the owner's backend. The other four operations need:

```
Authorization: Bearer <BRIDGE_TOKEN>
```

The tenant key (`X-API-Key`) is not part of this contract: it lives in the bridge
environment and never reaches the browser.

## Idempotency

Every write carries `eventId` — the sender generates it, not the bridge. The rule
is simple: one fact — one `eventId`, forever. A retry with the same `eventId` must
not create a second accrual.

- the core answers `duplicate: true` if the event is already accepted;
- the bridge in queue mode puts the event into its outbox and answers `202`;
- `eventId` is at most 200 characters, usually `order:<id>`, `refund:<id>`,
  `member:<id>`, `claim:<code>:<client>`.

## Responses

| Operation | Response |
|---|---|
| `claim` | `{status, code?, sponsorId?, memberId?, claimedAt?, eventId?}` |
| `order`, `refund`, `member` | `{queued, eventId, engine?: {eventId, status, duplicate}}` |
| `partner-link` | `{code, url, expiresAt}` |

Fields not shown in the examples are kept: the contract is extensible and extra
fields from the core are not dropped. Clients must ignore unknown fields.

## Errors

| Code | When | Body |
|---|---|---|
| `400` | no partner code, broken body, bad link code | `{"detail": "..."}` |
| `401` | missing or wrong `Authorization` | `{"detail": "unauthorized"}` |
| `409` | rebinding to another partner, a taken code | `{"detail": "..."}` |
| `422` | body does not fit the schema | `{"detail": [...]}` |
| `429` | more than 30 `claim` per minute from one address | `{"detail": "too many claims"}` |
| `503` | token or tenant key is not configured | `{"detail": "..."}` |

## What counts as a compatible change

- adding optional fields to responses and new operations;
- new `status` values;
- widening allowed values, as long as clients already pass them through.

Incompatible: renaming or removing fields, changing what amounts mean, moving
routes, changing units. Amounts are always in minor units of the currency
(`amount: 500000` is 5,000.00).

## How the contract stays current

The schema is generated from the handlers themselves (`src/partna_bridge/spec.py`),
not written by hand:

```bash
uv run python scripts/export_spec.py          # refresh the snapshot
uv run python scripts/export_spec.py --check  # verify the snapshot is fresh
```

Tests in `tests/test_contract.py` check three things: the snapshot matches the
application, the contract holds exactly five operations, and the examples pass the
schemas. A mismatch fails the pipeline instead of reaching a client.
