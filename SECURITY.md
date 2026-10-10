# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Report it privately through GitHub: on this repository open **Security → Report a
vulnerability** (GitHub private vulnerability reporting). Include what you found, how to
reproduce it, and the impact you expect. We aim to acknowledge reports within a few working
days.

## Scope

In scope: code in this repository — the FastAPI backend (`apps/api`), the Next.js frontend
(`apps/web`), and the container/compose files.

Out of scope: vulnerabilities in third-party dependencies or external tools (report those
upstream), and any hosted deployment you do not operate yourself.

## Things to know when running it yourself

- **Trained model files are Python pickles.** Loading one executes arbitrary code. They are
  not distributed in git; train your own (`python -m apps.api.ml.training`) or verify the
  SHA-256 of any file you download before loading it.
- **The default database credentials in `docker-compose.yml` are for local development
  only.** Set your own `POSTGRES_PASSWORD` and `DATABASE_URL` for anything reachable from a
  network, and don't publish the database port.
- **Auth and credit/billing integrations are optional, and the API fails OPEN when they are
  not configured.** If neither `SUPABASE_JWT_SECRET` nor `SUPABASE_URL` is set, the auth
  middleware allows gated endpoints in an unauthenticated "soft mode" (it logs a warning)
  so local development works without Supabase. Never expose an instance configured that
  way to an untrusted network; configure auth, or put it behind your own access control.
- Keep the web app's `next` dependency current; framework-level cache and routing
  vulnerabilities are fixed upstream.

## Supported versions

Only the latest commit on `main` is supported.
