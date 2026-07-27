import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const projectRoot = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("https://visiondesk.example/", {
      headers: {
        accept: "text/html",
        host: "visiondesk.example",
        "x-forwarded-host": "visiondesk.example",
        "x-forwarded-proto": "https",
      },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the VisionDesk application shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>VisionDesk — Real-time Object Detection<\/title>/i);
  assert.match(html, /VisionDesk/);
  assert.match(html, /Quick start/i);
  assert.match(html, /Bring the scene into view/);
  assert.match(html, /Start camera/);
  assert.match(html, /Detection settings/);
  assert.doesNotMatch(html, /codex-preview|SkeletonPreview|react-loading-skeleton/i);
  assert.match(html, /https:\/\/visiondesk\.example\/og\.png/);
});

test("keeps the finished product modular and removes starter assets", async () => {
  const [page, layout, packageJson, hook, apiTypes] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../hooks/use-detection-socket.ts", import.meta.url), "utf8"),
    readFile(new URL("../types/detection.ts", import.meta.url), "utf8"),
  ]);

  assert.match(page, /from "@\/hooks\/use-camera"/);
  assert.match(page, /from "@\/hooks\/use-detection-socket"/);
  assert.match(page, /<CameraStage/);
  assert.match(page, /<ControlPanel/);
  assert.match(hook, /type:\s*"configure"/);
  assert.match(hook, /settings\.classes\.length === 0 \? null/);
  assert.match(apiTypes, /export interface DetectionResult/);
  assert.match(layout, /generateMetadata/);
  assert.match(layout, /\/og\.png/);
  assert.doesNotMatch(page, /_sites-preview|codex-preview/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);

  await access(new URL("../public/og.png", import.meta.url));
  await assert.rejects(
    access(new URL("../app/_sites-preview/SkeletonPreview.tsx", import.meta.url)),
  );
  await assert.rejects(
    access(new URL("public/favicon.svg", projectRoot)),
  );
});
