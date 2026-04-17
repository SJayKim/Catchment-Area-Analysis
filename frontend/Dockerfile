FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_KAKAO_MAP_KEY
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV NEXT_PUBLIC_KAKAO_MAP_KEY=$NEXT_PUBLIC_KAKAO_MAP_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL
# 빌드 타임 env 가드 — 빈 값/잘못된 값으로 이미지 빌드되는 것을 차단
RUN test -n "$NEXT_PUBLIC_KAKAO_MAP_KEY" || \
    (echo "ERROR: NEXT_PUBLIC_KAKAO_MAP_KEY build arg required" >&2; exit 1)
RUN echo "$NEXT_PUBLIC_API_URL" | grep -Eqv '/api/?$' || \
    (echo "ERROR: NEXT_PUBLIC_API_URL must not end with /api (frontend auto-appends /api)" >&2; exit 1)
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
