# Стадия сборки (Vite) → образ Caddy, раздающий статику SPA + проксирующий /api
# и терминирующий TLS (один веб-контейнер вместо nginx+Caddy).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci 2>/dev/null || npm install
COPY . .
RUN npm run build

FROM caddy:2
# Собранная статика; Caddyfile монтируется из compose (правится без пересборки).
COPY --from=build /app/dist /srv
EXPOSE 80 443
