# Changelog

## 0.2.0

- `POST /v1/member`: the owner's own graph, the host reports who invited whom.
- Typed request bodies for `order`, `refund` and `member`: `/openapi.json` is now a contract an agent
  can read, instead of a free-form object.
- Server-side `claim`: a call with the bearer token is not limited by the browser rate limit, so a
  backend can claim every signup.
- Integration levels 1–4 in `docs/integrations/`, `llms.txt` for agents, `skills/integrate-partna-bridge`.
- `scripts/smoke.sh` walks a level against a live bridge and prints what passed.

## 0.1.0

First public version.

- REST bridge between a client site and the partner engine: `config`, `claim`, `partner-link`,
  `order`, `refund`.
- Partner binding in an `HttpOnly` cookie on the client domain, `?ref=` redirect after `/r/<code>`.
- Server-to-server calls protected by a bearer token, so the frontend cannot award commissions.
- Signed webhooks with deduplication by `eventId`, plus an inbox listing.
- Outbox with SQLite persistence, backoff retries and manual retry endpoint; `inline` mode for
  synchronous delivery.
- `/health` reports whether the tenant key is configured; protected endpoints answer `503` until it
  is.
- `install.sh`: generates secrets, builds the container, waits for health and prints next steps.
- MIT license.
