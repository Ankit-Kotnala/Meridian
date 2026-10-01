FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS base
RUN corepack enable && corepack prepare npm@11.8.0 --activate
WORKDIR /workspace

FROM base AS dependencies
COPY package.json package-lock.json ./
COPY patches ./patches
COPY frontend/web/package.json ./frontend/web/package.json
COPY shared/contracts/package.json ./shared/contracts/package.json
COPY frontend/design-tokens/package.json ./frontend/design-tokens/package.json
COPY frontend/eslint-config/package.json ./frontend/eslint-config/package.json
COPY frontend/test-fixtures/package.json ./frontend/test-fixtures/package.json
COPY frontend/typescript-config/package.json ./frontend/typescript-config/package.json
COPY frontend/ui/package.json ./frontend/ui/package.json
RUN npm ci

FROM base AS builder
ARG NEXT_PUBLIC_UPLOAD_ORIGIN=http://localhost:9000
ENV NEXT_PUBLIC_UPLOAD_ORIGIN=$NEXT_PUBLIC_UPLOAD_ORIGIN
COPY --from=dependencies /workspace /workspace
COPY frontend/web ./frontend/web
COPY shared/contracts ./shared/contracts
COPY frontend/design-tokens ./frontend/design-tokens
COPY frontend/typescript-config ./frontend/typescript-config
COPY frontend/ui ./frontend/ui
WORKDIR /workspace/frontend/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build --workspace=@rezumi/contracts && npm run build --workspace=@rezumi/web

FROM builder AS production-dependencies
WORKDIR /workspace
RUN npm prune --omit=dev --workspaces --include-workspace-root=false --package-lock=false

FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
    && rm -f /usr/local/bin/corepack /usr/local/bin/npm /usr/local/bin/npx \
        /usr/local/bin/pnpm /usr/local/bin/pnpx /usr/local/bin/yarn \
        /usr/local/bin/yarnpkg \
    && addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs
COPY --from=production-dependencies --chown=nextjs:nodejs /workspace/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /workspace/frontend/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /workspace/frontend/web/.next/static ./frontend/web/.next/static
WORKDIR /app/frontend/web
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
