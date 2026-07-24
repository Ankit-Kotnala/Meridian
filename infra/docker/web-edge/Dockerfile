FROM node:24-alpine@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd

# The edge only executes server.mjs. Remove build/package-management tooling from
# the shipped runtime so npm's transitive packages are not part of the attack
# surface.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
    && rm -f /usr/local/bin/corepack /usr/local/bin/npm /usr/local/bin/npx \
        /usr/local/bin/pnpm /usr/local/bin/pnpx /usr/local/bin/yarn \
        /usr/local/bin/yarnpkg

WORKDIR /app
COPY --chown=node:node infra/docker/web-edge/server.mjs ./server.mjs
USER node
EXPOSE 8080
CMD ["node", "/app/server.mjs"]
