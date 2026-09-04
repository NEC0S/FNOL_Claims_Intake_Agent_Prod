# ---- Build stage -----------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .
# VITE_API_BASE_URL is baked in at build time if provided; otherwise the app
# calls relative "/api", which nginx proxies to $BACKEND_URL at runtime.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- Runtime stage ----------------------------------------------------------
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Render (and most PaaS) inject $PORT; BACKEND_URL points at the API service
# (e.g. http://backend:8000 in docker-compose, or the backend's public
# Render URL when deployed as two separate services).
ENV PORT=8080
ENV BACKEND_URL=http://backend:8000

EXPOSE 8080

CMD ["sh", "-c", "envsubst '${PORT} ${BACKEND_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
