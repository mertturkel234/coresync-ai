# Acme Orders Integration Guide

## Authentication

Every sandbox request must include the `X-Sandbox-Key` header containing a scoped, non-expired sandbox credential (`csk_<public_id>_<secret>`). Never hardcode credentials in source control; read `CORESYNC_SANDBOX_KEY` from environment variables.

## Error Handling and Retries

- `401 Unauthorized`: The sandbox credential is missing, expired, revoked, or scoped to a different project.
- `422 Unprocessable Entity`: Check `customer_ref`, `currency` (`USD`, `EUR`, or `GBP`), and line-item quantities.
- `429 Too Many Requests`: Respect the `Retry-After` header before retrying.

## Quick Verification Flow

1. Call `GET /demo/orders` to inspect seeded synthetic orders (`ord_1001`, `ord_1002`).
2. Call `POST /demo/orders` with `customer_ref`, `currency`, and at least one item to create a new order.
3. Call `GET /demo/orders/{order_id}` to fetch a specific order.
