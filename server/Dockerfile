FROM node:20-alpine

# Enable pnpm
RUN corepack enable pnpm

WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install only production dependencies if possible, 
# but since tsx is in devDependencies and we use it to run server,
# we install all dependencies.
RUN pnpm install --frozen-lockfile

# Copy server source code
# We also copy shared/ if it exists (as index.ts might import from shared)
COPY server/ ./server/
COPY shared/ ./shared/
COPY tsconfig.json .

# Expose orbit-service port
EXPOSE 8081

# Command to run orbit-service
CMD ["pnpm", "run", "orbit-service"]
