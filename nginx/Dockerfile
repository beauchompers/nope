# Build frontend
FROM node:22-alpine AS frontend-build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Final nginx image
FROM nginx:alpine

# Install openssl for certificate generation
RUN apk add --no-cache openssl apache2-utils

# Copy nginx config template (processed at runtime by entrypoint)
COPY nginx/nginx.conf.template /etc/nginx/nginx.conf.template

# Copy frontend build
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# Copy entrypoint script
COPY nginx/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Default port (can be overridden via LISTEN_PORT env var)
EXPOSE 8081

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
