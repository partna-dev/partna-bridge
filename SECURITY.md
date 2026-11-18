# Security policy

## Reporting a vulnerability

Write to `pavel@partna.dev` with a short description, the affected version or commit, and how to
reproduce it. Do not open a public issue for a vulnerability.

You can expect an answer within three working days. If the report is confirmed, the fix and a short
advisory are published together, and you are credited unless you prefer otherwise.

## Scope

In scope:

- the tenant key leaking to the browser or into logs;
- forged webhooks accepted without a valid `X-Partner-Signature`;
- bypassing the bearer token on `order`, `refund`, `partner-link` and outbox endpoints;
- a binding cookie that can be set or read from another domain;
- rate-limit bypass on `claim` that allows unbounded writes.

Out of scope:

- denials of service that require flooding the host;
- issues that only appear with `BRIDGE_ALLOWED_ORIGINS=*`;
- the behaviour of the partner engine behind `BRIDGE_ENGINE_URL` — report that separately.

## What this service must never do

- store money or perform payouts;
- return `BRIDGE_ENGINE_API_KEY` or `BRIDGE_BRIDGE_TOKEN` in any response;
- accept a webhook whose signature does not match the raw request body.
