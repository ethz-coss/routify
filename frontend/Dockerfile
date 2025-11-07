# Multi-stage build for Angular frontend
FROM node:18-alpine AS build

# Build metadata (overridable via build args)
ARG FRONTEND_VERSION="dev_local"
ARG GIT_COMMIT_HASH="unknown"
ARG BUILD_DATE="unknown"

# Install git for version generation
RUN apk add --no-cache git

# Set working directory
WORKDIR /app

# Expose build metadata to the build process
ENV FRONTEND_VERSION=${FRONTEND_VERSION}
ENV GIT_COMMIT_HASH=${GIT_COMMIT_HASH}
ENV BUILD_DATE=${BUILD_DATE}

# Copy package files
COPY package*.json ./
COPY angular.json ./
COPY tsconfig*.json ./

# Install patch-package globally first to satisfy postinstall scripts from dependencies
RUN npm install -g patch-package

# Install all dependencies (including dev dependencies for build)
RUN npm install

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Build the application
RUN npm run build

# Production stage with nginx
FROM nginx:alpine

# Install curl for readiness checks
RUN apk add --no-cache curl

# Copy built application from build stage
COPY --from=build /app/dist/routify /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
