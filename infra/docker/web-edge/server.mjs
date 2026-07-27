import http from "node:http";

import {
  downstreamHeaders,
  exactUploadOrigin,
  upstreamHeaders,
} from "./header-policy.mjs";

const listenPort = boundedPort(process.env.PORT ?? "8080");
const upstreamPort = boundedPort(process.env.UPSTREAM_PORT ?? "3000");
const upstreamHost = safeHostname(process.env.UPSTREAM_HOST ?? "web");
const uploadOrigin = exactUploadOrigin(
  process.env.EDGE_UPLOAD_ORIGIN ?? "http://localhost:9000",
);
const hstsEnabled = strictBoolean(
  process.env.EDGE_ENABLE_HSTS ?? "false",
  "EDGE_ENABLE_HSTS",
);

const server = http.createServer((request, response) => {
  const upstream = http.request(
    {
      host: upstreamHost,
      port: upstreamPort,
      method: request.method,
      path: request.url,
      headers: upstreamHeaders(request.headers, request.socket.remoteAddress),
    },
    (upstreamResponse) => {
      response.writeHead(
        upstreamResponse.statusCode ?? 502,
        upstreamResponse.statusMessage,
        downstreamHeaders(upstreamResponse.headers, hstsEnabled, uploadOrigin),
      );
      upstreamResponse.pipe(response);
    },
  );

  upstream.on("error", () => {
    if (response.headersSent) {
      response.destroy();
      return;
    }
    response.writeHead(
      502,
      downstreamHeaders(
        {
          "cache-control": "no-store",
          "content-type": "application/problem+json",
        },
        hstsEnabled,
        uploadOrigin,
      ),
    );
    response.end(
      JSON.stringify({
        type: "about:blank",
        title: "Web application unavailable",
        status: 502,
        detail: "The web application could not be reached.",
      }),
    );
  });
  request.on("aborted", () => upstream.destroy());
  request.pipe(upstream);
});

server.headersTimeout = 10_000;
server.requestTimeout = 130_000;
server.keepAliveTimeout = 5_000;
server.listen(listenPort, "0.0.0.0");

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}

function boundedPort(value) {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error("Edge proxy ports must be integers between 1 and 65535.");
  }
  return port;
}

function strictBoolean(value, name) {
  if (value === "true") return true;
  if (value === "false") return false;
  throw new Error(`${name} must be true or false.`);
}

function safeHostname(value) {
  if (!/^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$/u.test(value)) {
    throw new Error("UPSTREAM_HOST must be a plain hostname.");
  }
  return value;
}
