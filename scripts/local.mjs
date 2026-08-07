#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const docker = process.platform === "win32" ? "docker.exe" : "docker";
const pnpm = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const uv = process.platform === "win32" ? "uv.exe" : "uv";

const dependencyServices = [
  "postgres",
  "redis",
  "minio",
  "minio-init",
  "mailpit",
  "clamav",
];
const backendServices = [
  ...dependencyServices,
  "api",
  "worker",
  "worker-scheduler",
];
const webServices = ["web", "web-edge"];
const serviceNames = new Set([...backendServices, ...webServices]);

function usage() {
  console.log(`Rezumi local development

Usage: node scripts/local.mjs <command> [target]

Commands:
  up [full|backend|dependencies]  Start a detached healthy local stack
  rebuild [all|backend|web]       Rebuild only the changed runtime surface
  dev-web                         Backend containers + Next.js hot reload
  dev-api                         Dependency containers + FastAPI hot reload
  dev-worker                      Dependency containers + local Celery worker
  status                          Show Compose service state
  logs [service]                  Follow all logs or one allowlisted service
  smoke [full|backend]            Probe the running local services
  down                            Stop services while preserving volumes
  help                            Show this help

Normal commands never delete volumes. Database reset remains an explicit Make target.`);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    env: options.env ?? process.env,
    stdio: "inherit",
    windowsHide: true,
    shell: process.platform === "win32" && command.endsWith(".cmd"),
  });
  if (result.error) {
    console.error(`Unable to run ${command}: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function compose(args) {
  run(docker, ["compose", ...args]);
}

function readLocalEnvironment() {
  const values = {};
  for (const filename of [".env.example", ".env"]) {
    const path = resolve(root, filename);
    if (!existsSync(path)) continue;
    for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const separator = line.indexOf("=");
      if (separator < 1) continue;
      const key = line.slice(0, separator).trim();
      let value = line.slice(separator + 1).trim();
      if (
        value.length >= 2 &&
        ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'")))
      ) {
        value = value.slice(1, -1);
      }
      values[key] = value;
    }
  }
  return { ...values, ...process.env };
}

function hostEnvironment() {
  const local = readLocalEnvironment();
  const postgresPort = local.POSTGRES_PORT || "55432";
  const redisPort = local.REDIS_PORT || "6379";
  const minioPort = local.MINIO_API_PORT || "9000";
  const clamavPort = local.CLAMAV_PORT || "3310";
  const smtpPort = local.MAILPIT_SMTP_PORT || "1025";
  const apiPort = local.API_PORT || "8000";
  const postgresUser = encodeURIComponent(local.POSTGRES_USER || "rezumi");
  const postgresPassword = encodeURIComponent(
    local.POSTGRES_PASSWORD || "change-me-local-only",
  );
  const postgresDatabase = encodeURIComponent(local.POSTGRES_DB || "rezumi");
  const databaseUrl = `postgresql+asyncpg://${postgresUser}:${postgresPassword}@127.0.0.1:${postgresPort}/${postgresDatabase}`;
  const redisUrl = `redis://127.0.0.1:${redisPort}/0`;
  const resultBackend = `redis://127.0.0.1:${redisPort}/1`;
  const objectEndpoint = `http://localhost:${minioPort}`;
  const apiBaseUrl = `http://localhost:${apiPort}`;

  return {
    ...local,
    API_BASE_URL: apiBaseUrl,
    API_BFF_CLIENT_SIGNAL_SECRET:
      local.API_BFF_CLIENT_SIGNAL_SECRET ||
      local.BFF_CLIENT_SIGNAL_SECRET ||
      "change-me-local-only-bff-client-signal-secret",
    REZUMI_CLAMAV_HOST: "127.0.0.1",
    REZUMI_CLAMAV_PORT: clamavPort,
    REZUMI_DATABASE_URL: databaseUrl,
    REZUMI_REDIS_URL: redisUrl,
    REZUMI_S3_ENDPOINT_URL: objectEndpoint,
    REZUMI_S3_PUBLIC_ENDPOINT_URL: objectEndpoint,
    REZUMI_SMTP_HOST: "127.0.0.1",
    REZUMI_SMTP_PORT: smtpPort,
    CELERY_BROKER_URL: redisUrl,
    CELERY_RESULT_BACKEND: resultBackend,
    CLAMAV_HOST: "127.0.0.1",
    CLAMAV_PORT: clamavPort,
    DATABASE_URL: databaseUrl,
    NEXT_PUBLIC_API_BASE_URL: apiBaseUrl,
    NEXT_PUBLIC_APP_URL:
      local.PUBLIC_APP_URL ||
      local.NEXT_PUBLIC_APP_URL ||
      "http://localhost:3000",
    NEXT_PUBLIC_UPLOAD_ORIGIN: objectEndpoint,
    REDIS_URL: redisUrl,
    S3_ENDPOINT_URL: objectEndpoint,
    S3_PUBLIC_ENDPOINT_URL: objectEndpoint,
    SMTP_HOST: "127.0.0.1",
    SMTP_PORT: smtpPort,
  };
}

function startServices(services, { build = false } = {}) {
  const args = ["up", "--detach", "--wait", "--wait-timeout", "300"];
  if (build) args.push("--build");
  compose([...args, ...services]);
}

function migrateDatabase() {
  compose([
    "run",
    "--rm",
    "--no-deps",
    "api",
    "alembic",
    "-c",
    "packages/backend/alembic.ini",
    "upgrade",
    "head",
  ]);
}
function stopServices(services) {
  compose(["stop", ...services]);
}

async function smoke(target) {
  const local = readLocalEnvironment();
  const apiPort = local.API_PORT || "8000";
  const webPort = local.WEB_PORT || "3000";
  const mailpitPort = local.MAILPIT_HTTP_PORT || "8025";
  const probes = [
    ["API liveness", `http://127.0.0.1:${apiPort}/health`],
    ["API readiness", `http://127.0.0.1:${apiPort}/ready`],
    ["API metadata", `http://127.0.0.1:${apiPort}/api/v1/meta`],
    ["Mailpit", `http://127.0.0.1:${mailpitPort}/api/v1/info`],
  ];
  if (target === "full") {
    probes.unshift(["Web", `http://127.0.0.1:${webPort}/api/health`]);
  }
  let failed = false;
  for (const [label, url] of probes) {
    try {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(10_000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      console.log(`PASS  ${label}  ${url}`);
    } catch (error) {
      failed = true;
      console.error(`FAIL  ${label}  ${url}  ${error.message}`);
    }
  }
  if (failed) process.exit(1);
}

const [command = "help", target] = process.argv.slice(2);

switch (command) {
  case "help":
  case "--help":
  case "-h":
    usage();
    break;
  case "up": {
    const selected = target || "full";
    if (selected === "full") startServices([], { build: true });
    else if (selected === "backend")
      startServices(backendServices, { build: true });
    else if (selected === "dependencies") startServices(dependencyServices);
    else {
      console.error(`Unknown up target: ${selected}`);
      process.exit(2);
    }
    break;
  }
  case "rebuild": {
    const selected = target || "all";
    if (selected === "all") startServices([], { build: true });
    else if (selected === "backend") {
      startServices(["api", "worker", "worker-scheduler"], { build: true });
    } else if (selected === "web") startServices(webServices, { build: true });
    else {
      console.error(`Unknown rebuild target: ${selected}`);
      process.exit(2);
    }
    break;
  }
  case "dev-web":
    stopServices(webServices);
    startServices(backendServices);
    run(pnpm, ["--filter", "@rezumi/web", "dev"], { env: hostEnvironment() });
    break;
  case "dev-api":
    stopServices(["api"]);
    startServices(dependencyServices);
    run(
      uv,
      [
        "run",
        "--package",
        "rezumi-api",
        "uvicorn",
        "rezumi_api.main:app",
        "--reload",
        "--port",
        readLocalEnvironment().API_PORT || "8000",
      ],
      { env: hostEnvironment() },
    );
    break;
  case "dev-worker":
    stopServices(["worker"]);
    startServices(dependencyServices);
    run(
      uv,
      [
        "run",
        "--package",
        "rezumi-worker",
        "celery",
        "--app",
        "rezumi_worker.app:celery_app",
        "worker",
        "--loglevel=INFO",
        ...(process.platform === "win32" ? ["--pool=solo", "--concurrency=1"] : []),
        "--queues=default,resume-health,resume-builder,career-record,maintenance",
      ],
      { env: hostEnvironment() },
    );
    break;
  case "status":
    compose(["ps"]);
    break;
  case "logs":
    if (target && !serviceNames.has(target)) {
      console.error(`Unknown service: ${target}`);
      process.exit(2);
    }
    compose(["logs", "--follow", "--tail", "200", ...(target ? [target] : [])]);
    break;
  case "smoke": {
    const selected = target || "full";
    if (selected !== "full" && selected !== "backend") {
      console.error(`Unknown smoke target: ${selected}`);
      process.exit(2);
    }
    await smoke(selected);
    break;
  }
  case "down":
    compose(["down", "--remove-orphans"]);
    break;
  default:
    console.error(`Unknown command: ${command}`);
    usage();
    process.exit(2);
}




