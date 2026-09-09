# HTTP onboarding

Start the loopback dashboard, read `/api/session`, then call authenticated
`GET /v1/health` and `GET /v1/capabilities`. Use an idempotency key on every
memory mutation.
