FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1

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
