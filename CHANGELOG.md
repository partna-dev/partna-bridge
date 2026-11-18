# Changelog

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
