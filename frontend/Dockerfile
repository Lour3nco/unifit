# 1) build: gera os arquivos estáticos em /app/dist
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# a API é acessada pelo mesmo endereço do site, em /api (o nginx repassa para o backend)
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# 2) produção: só o nginx servindo os estáticos (sem Node, sem servidor de desenvolvimento)
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
