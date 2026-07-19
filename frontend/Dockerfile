# Multi-stage build producing Next.js's standalone output (see
# next.config.ts's `output: "standalone"`) so the runtime image only carries
# the trimmed server + its actual node_modules subset, not the full dev tree.
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# BACKEND_URL only matters at runtime (next.config.ts reads it when the
# server starts), but next.config.ts is still evaluated during the build for
# validation -- a placeholder here is harmless.
ENV BACKEND_URL=http://backend:8000
RUN npx next build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
# The standalone server binds to localhost unless told otherwise -- it has
# to listen on all interfaces to be reachable from outside the container.
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
