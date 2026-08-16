FROM node:20-alpine

# Enable pnpm
RUN corepack enable pnpm

WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --no-frozen-lockfile

# Copy orbit-service source code
# We also copy shared/ if it exists (as index.ts might import from shared)
COPY orbit-service/ ./orbit-service/
COPY shared/ ./shared/
COPY tsconfig.json .

# Expose orbit-service port
EXPOSE 8081

# Command to run orbit-service
CMD ["pnpm", "run", "orbit-service"]
