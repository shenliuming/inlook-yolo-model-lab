FROM node:20-alpine AS build

WORKDIR /app

COPY apps/yolo-web/package.json apps/yolo-web/package-lock.json ./
RUN npm ci

COPY apps/yolo-web/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
