# ── Build stage ──────────────────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app

# Install dependencies — frozen lockfile ensures reproducible builds
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

# Copy source
COPY . .

# VITE_API_URL must be set at build time (Vite bakes it in at compile time).
# In Docker Compose this is passed via --build-arg.
# On Vercel this is set as an environment variable in the project settings.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Production stage ─────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production

# Non-root nginx user (nginx:1.27-alpine already includes the nginx user)
RUN rm -rf /usr/share/nginx/html/*

# Copy the production build
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Health check — nginx serves index.html at root
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ > /dev/null || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
