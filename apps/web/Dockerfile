FROM node:22-alpine AS base
WORKDIR /app

FROM base AS deps
COPY apps/web/package.json ./
RUN npm install

FROM base AS builder
# Next.js inlines NEXT_PUBLIC_* env vars into the client bundle at COMPILE
# time, so they must be supplied as build ARGs — not just runtime env.
# Each ARG falls back to a sensible local-dev default; production values
# are passed from docker-compose.prod.yml's `build.args`.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_LEIL_API_URL=https://www.leil.app/api/v1

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_LEIL_API_URL=$NEXT_PUBLIC_LEIL_API_URL

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
