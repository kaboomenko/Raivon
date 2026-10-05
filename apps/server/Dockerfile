# Raivon API image. Build from the repo root: docker build -f apps/server/Dockerfile -t raivon-api .
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/server/package.json apps/server/
RUN npm ci -w @raivon/server --include-workspace-root=false --omit=dev || npm install -w @raivon/server --omit=dev
COPY apps/server apps/server
WORKDIR /app/apps/server
ENV NODE_ENV=production PORT=8080
EXPOSE 8080
CMD ["npx", "tsx", "src/index.ts"]
