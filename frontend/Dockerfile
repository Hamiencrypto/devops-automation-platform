# ---------------------------------------------------------------------
# 1) Build stage
# ---------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# NEXT_PUBLIC_* env vars are inlined into the client bundle during
# `npm run build`. Accept them as build args so the compose file can
# override them.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

# More resilient npm settings for flaky networks
RUN npm config set fetch-retries 5 \
 && npm config set fetch-retry-mintimeout 20000 \
 && npm config set fetch-retry-maxtimeout 120000 \
 && npm config set fetch-timeout 600000

COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps --no-audit --no-fund \
 || (sleep 5 && npm install --legacy-peer-deps --no-audit --no-fund)

COPY . .
RUN npm run build

# ---------------------------------------------------------------------
# 2) Runtime stage
# ---------------------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/package.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

CMD ["npm", "run", "start"]
