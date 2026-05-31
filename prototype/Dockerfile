FROM node:20-alpine AS build

WORKDIR /app/prototype

COPY prototype/package.json prototype/package-lock.json ./
RUN npm ci

COPY prototype/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/prototype/dist /usr/share/nginx/html

EXPOSE 80

