# Stage 1: Build the frontend
FROM node:20-alpine AS builder

# Enable pnpm
RUN corepack enable pnpm

WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --no-frozen-lockfile

# Copy source code
COPY . .

# Build the app using Vite
# We pass environment variables if needed, but for runtime URLs we rely on relative paths or runtime injection.
# However, Vite embeds env vars at build time. For docker-compose, we can pass them as build args,
# but it's often easier to just build and let the default localhost endpoints work or configure proxy.
# Since we are putting it in Nginx, Vite needs the env vars during build.
ARG VITE_ORBIT_SERVICE_URL
ARG VITE_AI_SERVICE_URL
ENV VITE_ORBIT_SERVICE_URL=$VITE_ORBIT_SERVICE_URL
ENV VITE_AI_SERVICE_URL=$VITE_AI_SERVICE_URL

RUN pnpm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY client/nginx.conf /etc/nginx/conf.d/default.conf

# Expose the configured port
EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
