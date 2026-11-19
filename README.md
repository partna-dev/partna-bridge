# partna-bridge

[Русский](README.ru.md)

Small self-hosted service that sits between a customer's website and the partner-program engine:
it keeps the tenant key on the server, holds the partner binding in an `HttpOnly` cookie, and
receives signed webhooks.

[![ci](https://github.com/partna-dev/partna-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/partna-dev/partna-bridge/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Обзор, установка и глоссарий — в документации: https://partna.dev/docs/

## Contract

The five write operations — `claim`, `member`, `order`, `refund`, `partner-link` —
are described in [`spec/partna-facts.v1.json`](spec/partna-facts.v1.json)
(OpenAPI 3.1); rules and examples are in [`spec/README.md`](spec/README.md). The
schema is generated from the handlers, so it cannot drift from the code.

## Why a bridge

An integration usually starts with the frontend calling the partner API directly. That works until
someone reads the network tab:

- **The key stays on the server.** `BRIDGE_ENGINE_API_KEY` lives in the bridge environment and never
  reaches the browser.
- **The partner code survives the session.** It is stored in an `HttpOnly` cookie on the customer's
  own domain, not in `sessionStorage` of one tab, so a visitor can close the page and come back to
  a purchase a week later and still be attributed.
- **One public webhook address.** The engine calls the bridge; signature verification and the inbox
  live in one place instead of being spread across the customer's project.

## Architecture

```mermaid
flowchart LR
  V[Visitor] -->|"/r/CODE"| B[Bridge]
  B -->|"Set-Cookie: HttpOnly"| V
  F[Client frontend] -->|"config, claim"| B
  S[Client backend] -->|"order, refund, partner-link"| B
  B -->|"X-API-Key"| E[Partner engine]
  E -->|"webhook, signed"| B
```

Money never passes through the bridge. It is a proxy with a cookie, a queue and a signature check.

## Quick start

```bash
./scripts/install.sh
```

The script creates `.env`, generates secrets, builds the container, waits for `/health` and prints
what is left to do. Details and checks are in [INSTALL.md](INSTALL.md); agent-oriented notes are in
[AGENTS.md](AGENTS.md).

Until an engine key is set, `/health` reports `key_configured: false` and protected endpoints answer
`503`. That is expected, not a failure.

## Configuration

| Variable | Meaning |
|---|---|
| `BRIDGE_ENGINE_URL` | address of the partner engine |
| `BRIDGE_ENGINE_API_KEY` | tenant key, server-side only |
| `BRIDGE_PUBLIC_URL` | public address of the bridge; the cookie `Secure` flag depends on it |
| `BRIDGE_DESTINATION_URL` | where to send a visitor after `/r/<code>` |
| `BRIDGE_BRIDGE_TOKEN` | bearer token for server-to-server calls: order, refund, partner link |
| `BRIDGE_WEBHOOK_SECRET` | shared secret for webhook signatures |
| `BRIDGE_ALLOWED_ORIGINS` | comma-separated frontend origins allowed by CORS |
| `BRIDGE_COOKIE_DAYS` | binding cookie lifetime, 30 by default |

`BRIDGE_BRAND`, `BRIDGE_CURRENCY` and the outbox settings are documented in [.env.example](.env.example).

## Endpoints

| Endpoint | Caller | Purpose |
|---|---|---|
| `GET /health` | monitoring | alive, is the key configured |
| `GET /v1/config` | frontend | brand, currency, destination address |
| `GET /r/<code>` | visitor | sets the cookie and redirects back with `?ref=<code>` |
| `POST /v1/claim` | frontend | binds the client to a code (from the body or the cookie) |
| `POST /v1/partner-link` | server | partner referral link |
| `POST /v1/order` | server | payment |
| `POST /v1/refund` | server | refund |
| `POST /webhooks/engine` | engine | event delivery, `X-Partner-Signature` |

`order` and `refund` require `Authorization: Bearer <BRIDGE_BRIDGE_TOKEN>`. The frontend must never
call them: otherwise anyone could award themselves a commission.

## Integration levels

Pick the smallest level that closes the task; raising it later does not require undoing the previous one.

| Level | Owner does | Where |
|---|---|---|
| 1 — ready link | creates a partner in the cabinet, sends a link | [level-1-link.md](docs/integrations/level-1-link.md) |
| 2 — own signup | claims the member from its backend, shows the link in its cabinet | [level-2-signup.md](docs/integrations/level-2-signup.md) |
| 3 — own graph | sends `member` facts from its own CRM | [level-3-own-graph.md](docs/integrations/level-3-own-graph.md) |
| 4 — own screens | shows balance and payouts inside its cabinet | [level-4-own-screens.md](docs/integrations/level-4-own-screens.md) |

Field reference: [docs/integrations/fields.md](docs/integrations/fields.md). Machine-readable contract:
`/openapi.json` of a running bridge. Check a level against a live bridge with
`./scripts/smoke.sh --level 2 --url https://bridge.example --token … --code … --user …`.

## Delivery queue

`BRIDGE_OUTBOX_MODE=queue` (default) writes orders and refunds to SQLite and answers `202`; a worker
retries with backoff. `inline` sends immediately and fails loudly when the engine is unreachable.

| Endpoint | Purpose |
|---|---|
| `GET /v1/outbox` | queue entries: status, attempts, error |
| `POST /v1/outbox/{id}/retry` | manual retry |
| `GET /v1/inbox` | accepted webhooks, deduplicated by `eventId` |

## Security model

- The tenant key is used only for outbound calls to the engine.
- The binding cookie is `HttpOnly`, `SameSite=Lax` and gets `Secure` when `BRIDGE_PUBLIC_URL` is
  `https`.
- Webhooks are rejected unless the signature over the raw body matches `BRIDGE_WEBHOOK_SECRET`.
- `claim` is rate-limited to 30 requests per minute per address; beyond that a proxy is expected.
- No personal data is stored: only client identifiers the site already passes.

## Boundaries

- No money is held and no payouts are made here.
- No payment provider integration: the host's own webhook handler posts the order. Request examples
  are in [INSTALL.md](INSTALL.md), section «Подключение к вебхуку платёжки».
- The processed `eventId` list lives in memory: after a restart a repeated event passes again, so the
  host should still deduplicate on its side.
- Not a billing system, not an analytics platform, not a CDN.

## Development

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check src tests
```

The tests cover the parts that actually break in production: the key never appears in responses, the
cookie is set and survives, an order without the bearer token is refused, a webhook with a bad
signature is dropped, and a repeated event is marked as such.

## Read more

- [Why your frontend should not talk to your partner API](https://dev.to/partna/your-frontend-should-not-talk-to-your-partner-api-402o) — the
  three failure modes this service removes, with the reasoning behind each decision.
- Notes while building: [t.me/partnadev](https://t.me/partnadev).

## License

MIT. Русская версия — [README.ru.md](README.ru.md).
