# Deployment

This page covers running LeilMat somewhere other than your laptop. For a local setup see
[Getting started](getting-started.md).

> **Read the [security checklist](#security-checklist) before exposing anything.** Out of the box
> the API is configured for local development: it is **unauthenticated**, trusts only `localhost`
> origins, and the compose file uses well-known database credentials.

## What the repository gives you

`docker-compose.yml` is a **development** stack: it builds the API and web images, runs PostgreSQL
(with pgvector) and ChromaDB, publishes their ports, bind-mounts the source into the API container
and runs it with `--reload`. It is not a production configuration. A production deployment is
yours to assemble from the pieces below.

| Piece | How it runs |
|---|---|
| API | `apps/api/Dockerfile`, Python 3.11. Exposes port 8000. |
| Web | `apps/web/Dockerfile`, multi-stage on `node:22-alpine`, Next.js standalone server (`node server.js`) on port 3000. |
| PostgreSQL | Needed only for cloud-simulation job tracking. |
| ChromaDB | Optional; literature retrieval for the chat panel. |

## Production-shaped notes

**API command.** The image's default command uses `--reload`. Override it:

```
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=<your proxy's IP>
```

Prefer your proxy's address over `*` for `--forwarded-allow-ips`: with `*`, any client can forge
`X-Forwarded-For`, which affects rate limiting and logs.

**Models.** The images do not train models, and trained models are not in git. Train once and make
them available to the container: bake them into your image, or mount `models/` as a volume
(`python -m apps.api.ml.training`). Without them yield-strength requests fail with
`model file missing — run training first`.

**M3GNet weights.** The API image downloads the M3GNet checkpoint at build time
(`apps/api/ml/models/fetch_m3gnet_weights.py`) so a cold start never depends on a live network call.
It is best-effort: if the fetch fails the build continues and formation energy falls back to the
Miedema heuristic at runtime (and says so in `source`).

**Web build arguments.** Next.js inlines `NEXT_PUBLIC_*` variables **at build time**. Supply
`NEXT_PUBLIC_API_URL` (and the Supabase ones, if you use auth) as build arguments, not just runtime
environment. The list is in the [configuration reference](reference/configuration.md#web-app-build-time).

**Routing.** The simplest setup is same-origin: put one reverse proxy in front, send `/api/*` to the
API and everything else to the web app. That avoids cross-origin requests entirely; if you do serve
them from different origins, list the web origin in `CORS_ORIGINS`.

**Security headers.** The web app sends a Content-Security-Policy and the usual hardening headers (HSTS, `X-Frame-Options`,
`nosniff`, `Referrer-Policy`, `Permissions-Policy`); the API adds `nosniff`, `X-Frame-Options`, `Referrer-Policy` and HSTS.
The policy's `connect-src` is built from the `NEXT_PUBLIC_*` values **at build time** (`apps/web/lib/securityHeaders.ts`), so
changing your API, Supabase or billing URL means rebuilding the web image. If a proxy sits in front, do not strip or replace
these headers. The CSP is not nonce-based (`script-src` keeps `'unsafe-inline'` for Next's hydration scripts), so it limits
framing, plugins and where the page may connect, but it is not a full defence against script injection.

**Health checks.** Use `GET /health` — it touches no model, database or LLM. The `python:slim` base
has no `curl` or `wget`, so a container health check needs Python (`urllib`). `GET /api/health/models`
reports the live state of the prediction stack.

## Settings you almost certainly need

| Variable | Why |
|---|---|
| `CORS_ORIGINS` | Defaults to localhost only. Set it to your real origin(s), comma-separated. `*` is ignored on purpose (the API allows credentials). |
| `PUBLIC_APP_URL` | Used for links in notification emails. Defaults to `http://localhost:4000`. |
| `DATABASE_URL` | Replace the development credentials. |
| `SUPABASE_URL` (modern projects, JWKS) or `SUPABASE_JWT_SECRET` (legacy HS256) | Turn authentication on. See below. |
| `OPENROUTER_API_KEY` | Enables the AI panels. |
| `MP_API_KEY` | Materials Project lookups. |

Everything else is in the [configuration reference](reference/configuration.md).

## Security checklist

| | Do this |
|---|---|
| ☐ | **Configure authentication.** With neither `SUPABASE_JWT_SECRET` nor a Supabase URL (`SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_URL`) set, the API **fails open**: cost-bearing endpoints accept anonymous requests ("soft mode", logged as a warning). Set one, then confirm an anonymous `POST /api/chat/global` returns `401`. Note that only the cost-bearing prefixes are gated — see [Architecture](architecture.md#request-pipeline) for the exact list; `/api/predict` and other read-style endpoints are intentionally open. |
| ☐ | **Set `CORS_ORIGINS`** to exactly the origins you serve, nothing broader. |
| ☐ | **Replace the development database credentials** (`leilmat`/`leilmat`) and do **not** publish ports 5432 or 8001 outside a private network. |
| ☐ | **Keep Next.js patched.** Next.js has had vulnerabilities involving its internal request headers (for example `x-middleware-subrequest`); stay on a current release and consider stripping Next-internal request headers at your proxy. |
| ☐ | **Never commit `.env`**, and rotate any key that has ever been pasted into a chat, ticket or log. |
| ☐ | **Only load model files you trained or hash-verified.** They are pickles; loading one runs code. |
| ☐ | **Set spend limits** if you enable cloud simulations or LLM features: the `DAYTONA_*` caps and the LLM rate limit and daily budget (`GET /api/health/budget`). See [Cloud simulations](cloud-simulations.md#cost-guardrails). |
| ☐ | **Add an access layer** (VPN, SSO proxy, IP allow-list) if you must run without Supabase auth on a shared network. |

Report vulnerabilities privately — see [`SECURITY.md`](../SECURITY.md).
