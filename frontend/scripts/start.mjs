import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer, request as proxyRequest } from "node:http";
import path from "node:path";

import { startProdServer } from "vinext/server/prod-server";

const host = process.env.HOST ?? "0.0.0.0";
const port = Number.parseInt(process.env.PORT ?? "3000", 10);
const clientDirectory = path.resolve(process.cwd(), "dist", "client");

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".map", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".webp", "image/webp"],
  [".ico", "image/x-icon"],
  [".woff", "font/woff"],
  [".woff2", "font/woff2"],
]);

function resolveClientAsset(requestPath) {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(requestPath, "http://localhost").pathname);
  } catch {
    return null;
  }

  if (!pathname.startsWith("/assets/")) return null;

  const resolvedPath = path.resolve(clientDirectory, `.${pathname}`);
  const clientPrefix = `${clientDirectory}${path.sep}`;
  return resolvedPath.startsWith(clientPrefix) ? resolvedPath : null;
}

async function serveClientAsset(request, response, assetPath) {
  try {
    const assetStat = await stat(assetPath);
    if (!assetStat.isFile()) return false;

    response.writeHead(200, {
      "Cache-Control": "public, max-age=31536000, immutable",
      "Content-Length": String(assetStat.size),
      "Content-Type":
        contentTypes.get(path.extname(assetPath).toLowerCase()) ??
        "application/octet-stream",
    });

    if (request.method === "HEAD") {
      response.end();
    } else {
      createReadStream(assetPath).pipe(response);
    }
    return true;
  } catch {
    return false;
  }
}

function proxyToVinext(request, response, internalPort) {
  const upstream = proxyRequest(
    {
      hostname: "127.0.0.1",
      port: internalPort,
      path: request.url,
      method: request.method,
      headers: request.headers,
    },
    (upstreamResponse) => {
      response.writeHead(
        upstreamResponse.statusCode ?? 500,
        upstreamResponse.headers,
      );
      upstreamResponse.pipe(response);
    },
  );

  upstream.on("error", () => {
    if (!response.headersSent) {
      response.writeHead(502, { "Content-Type": "text/plain; charset=utf-8" });
    }
    response.end("Frontend server unavailable");
  });

  request.pipe(upstream);
}

const vinext = await startProdServer({
  host: "127.0.0.1",
  port: 0,
  outDir: path.resolve(process.cwd(), "dist"),
  purpose: "internal renderer",
});

const server = createServer(async (request, response) => {
  const assetPath = resolveClientAsset(request.url ?? "/");
  if (assetPath && (await serveClientAsset(request, response, assetPath))) {
    return;
  }

  proxyToVinext(request, response, vinext.port);
});

server.listen(port, host, () => {
  console.log(`\n  VisionDesk ready at http://127.0.0.1:${port}\n`);
});

function shutdown() {
  server.close(() => vinext.server.close(() => process.exit(0)));
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
