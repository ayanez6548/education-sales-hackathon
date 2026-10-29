FROM node:22-alpine AS build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* /web/
RUN npm install
COPY frontend /web
ARG VITE_API_URL=/
ARG VITE_DEMO_MODE=false
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
