# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json /app/
RUN --mount=type=cache,target=/root/.npm npm ci --prefer-offline

COPY frontend/tsconfig.json /app/tsconfig.json
COPY frontend/tsconfig.node.json /app/tsconfig.node.json
COPY frontend/vite.config.ts /app/vite.config.ts
COPY frontend/index.html /app/index.html
COPY frontend/src /app/src

RUN npm run build

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
