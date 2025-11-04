# Multi-stage build for Angular frontend
FROM node:18-alpine AS build

# Install git for version generation
RUN apk add --no-cache git

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY angular.json ./
COPY tsconfig*.json ./

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
