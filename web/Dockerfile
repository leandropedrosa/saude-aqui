# ---------------------------------------------------------------------
# Etapa 1: build do React com Node (só existe durante o build, no CI)
# ---------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# Variáveis VITE_* opcionais (provedor de tiles do mapa), fixadas no build
ARG VITE_TILES_URL=""
ARG VITE_TILES_ATRIBUICAO=""
RUN npm run build

# ---------------------------------------------------------------------
# Etapa 2: nginx servindo os arquivos estáticos (imagem final ~50 MB)
# ---------------------------------------------------------------------
FROM nginx:alpine
# Endereço interno da API (no Easypanel, ajuste para o nome do serviço)
ENV API_UPSTREAM=http://api:8000
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
