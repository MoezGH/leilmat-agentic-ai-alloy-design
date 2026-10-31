FROM node:22-alpine AS base
WORKDIR /app

FROM base AS deps
COPY apps/web/package.json ./
RUN npm install

FROM base AS builder
# Next.js inlines NEXT_PUBLIC_* env vars into the client bundle at COMPILE
# time, so they must be supplied as build ARGs — not just runtime env.
# Each ARG falls back to a sensible local-dev default; production values
# are passed as `build.args` by your deployment's compose file.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_LEIL_API_URL=
# The account app (profile, password, usage). Empty = the avatar menu offers no
# "Account settings" item at all, rather than linking somewhere the operator
# never named. Same rule as the billing URL above.
ARG NEXT_PUBLIC_ACCOUNT_URL=
# Parent domain for the Supabase session cookie, e.g. ".leil.app", so one
# sign-in covers every Leil app. Empty = host-only (local dev, or a
# self-hosted single app that owns no parent domain). See lib/authCookie.ts.
ARG NEXT_PUBLIC_AUTH_COOKIE_DOMAIN=

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_LEIL_API_URL=$NEXT_PUBLIC_LEIL_API_URL \
    NEXT_PUBLIC_ACCOUNT_URL=$NEXT_PUBLIC_ACCOUNT_URL \
    NEXT_PUBLIC_AUTH_COOKIE_DOMAIN=$NEXT_PUBLIC_AUTH_COOKIE_DOMAIN

COPY --from=deps /app/node_modules ./node_modules
COPY apps/web/ .
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
