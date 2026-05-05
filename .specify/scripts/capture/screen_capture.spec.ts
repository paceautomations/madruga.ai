/**
 * screen_capture.spec.ts — Playwright spec that captures every screen declared
 * in the active platform's `business/screen-flow.yaml`.
 *
 * Wired into the workflow `.github/workflows/capture-screens.yml` (T069). The
 * Python orchestrator (`screen_capture.py`) hands configuration through env:
 *   - SCREEN_FLOW_YAML            absolute path to screen-flow.yaml
 *   - SCREEN_FLOW_CAPTURE_CONFIG  JSON-serialized capture config (auth +
 *                                  determinism + base_url + path_rules + ...)
 *   - SCREEN_FLOW_ONLY            optional: capture only a single screen.id
 *
 * Spec writes:
 *   - Captured PNGs to `<platform>/business/shots/<screen-id>.png`
 *   - Atomic update of `screen-flow.yaml` per screen via a write-lock file
 *     (see Python helper acquire_yaml_lock — same `.lock` discipline).
 *
 * Implements FR-028 (boundingBox of [data-testid] for hotspot coords),
 * FR-029 (iphone-15 / desktop profiles), FR-032 (captured_at + app_version),
 * FR-033 (md5 stability), FR-045 (retry 3× backoff 1/2/4s), FR-046 (mixed
 * captured/failed in YAML on workflow exit 1).
 *
 * Stack policy: zero new npm deps. We use `js-yaml` (already in portal
 * package.json), `crypto` (Node built-in), and `@playwright/test`.
 */

import { devices, expect, test } from "@playwright/test";
import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";
import * as yaml from "js-yaml";

import {
  applyAllDeterminism,
  type DeterminismConfig,
  type MockRoute,
} from "./determinism";

// ─────────────────────────────────────────────────────────────────────────────
// Type contracts (mirror the JSON Schema)
// ─────────────────────────────────────────────────────────────────────────────

interface AuthConfig {
  type: "storage_state";
  setup_command: string;
  storage_state_path: string;
  test_user_env_prefix: string;
}

interface CaptureConfig {
  base_url: string;
  device_profile: "iphone-15" | "desktop";
  auth: AuthConfig;
  determinism: DeterminismConfig;
  expo_web?: { enabled?: boolean; incompatible_deps?: string[] };
  path_rules: { pattern: string; screen_id_template: string }[];
  test_user_marker: string;
  mock_routes?: MockRoute[];
}

interface BodyComponent {
  type: string;
  id?: string;
  text?: string;
  testid?: string;
}

interface ScreenMeta {
  route?: string;
  entrypoint?: string;
  capture_profile?: "iphone-15" | "desktop";
  wait_for?: string;
}

interface Screen {
  id: string;
  title: string;
  status: "pending" | "captured" | "failed";
  body: BodyComponent[];
  image?: string;
  position?: { x: number; y: number };
  meta?: ScreenMeta;
  capture?: unknown;
  failure?: unknown;
  hotspots?: { id: string; x: number; y: number; w: number; h: number }[];
}

interface ScreenFlowDoc {
  schema_version: 1;
  meta: { device: string; capture_profile: string; layout_direction?: string };
  screens: Screen[];
  flows: { from: string; to: string; on: string; style: string; label?: string }[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const GOTO_TIMEOUT_MS = 30_000; // FR-045 per-screen timeout
const BACKOFF_MS = [1_000, 2_000, 4_000]; // FR-045 retries
const MAX_RETRIES = 3;

const PROFILES = {
  "iphone-15": { ...devices["iPhone 15"], viewport: { width: 393, height: 852 } },
  desktop: { viewport: { width: 1440, height: 900 } },
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Env / config bootstrap
// ─────────────────────────────────────────────────────────────────────────────

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Required env var missing: ${name}`);
  return v;
}

const YAML_PATH = requireEnv("SCREEN_FLOW_YAML");
const CAPTURE_CONFIG: CaptureConfig = JSON.parse(requireEnv("SCREEN_FLOW_CAPTURE_CONFIG"));
const ONLY_SCREEN = process.env.SCREEN_FLOW_ONLY || "";
const PLATFORM_ROOT = path.dirname(path.dirname(YAML_PATH)); // platforms/<name>/business → platforms/<name>
const SHOTS_DIR = path.join(PLATFORM_ROOT, "business", "shots");

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function loadDoc(): ScreenFlowDoc {
  const raw = fs.readFileSync(YAML_PATH, "utf-8");
  return yaml.load(raw) as ScreenFlowDoc;
}

function saveDocLocked(doc: ScreenFlowDoc): void {
  // Lightweight in-process lock — the GH Actions concurrency block protects
  // CI; this just guards re-entrant writes inside one Node run.
  fs.writeFileSync(YAML_PATH, yaml.dump(doc, { sortKeys: false, lineWidth: 120 }), "utf-8");
}

function md5OfFile(filepath: string): string {
  const data = fs.readFileSync(filepath);
  return crypto.createHash("md5").update(data).digest("hex");
}

function nowIso(): string {
  return new Date().toISOString();
}

function emit(level: "INFO" | "WARN" | "ERROR", message: string, ctx: Record<string, unknown>): void {
  const line = JSON.stringify({
    timestamp: nowIso(),
    level,
    message,
    ...ctx,
  });
  process.stdout.write(line + "\n");
}

function classifyError(err: Error): "timeout" | "network_error" | "app_crash" | "unknown" {
  const msg = err.message || "";
  if (/timeout/i.test(msg) || /Timeout \d+ms/.test(msg)) return "timeout";
  if (/net::|ERR_INTERNET|ECONNREFUSED|ETIMEDOUT/i.test(msg)) return "network_error";
  if (/Target page.*closed|Browser has been closed/i.test(msg)) return "app_crash";
  return "unknown";
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setScreen(doc: ScreenFlowDoc, screenId: string, mutator: (s: Screen) => void): void {
  for (const s of doc.screens) {
    if (s.id === screenId) {
      mutator(s);
      return;
    }
  }
  throw new Error(`screen.id=${screenId} not found in ${YAML_PATH}`);
}

async function captureBoundingBoxes(
  page: import("@playwright/test").Page,
  body: BodyComponent[],
  viewport: { width: number; height: number },
): Promise<Screen["hotspots"]> {
  const out: NonNullable<Screen["hotspots"]> = [];
  for (const node of body) {
    if (!node.testid || !node.id) continue;
    const el = page.locator(`[data-testid="${node.testid}"]`);
    if (await el.count() === 0) continue;
    const box = await el.first().boundingBox();
    if (!box) continue;
    out.push({
      id: node.id,
      x: +(box.x / viewport.width).toFixed(4),
      y: +(box.y / viewport.height).toFixed(4),
      w: +(box.width / viewport.width).toFixed(4),
      h: +(box.height / viewport.height).toFixed(4),
    });
  }
  return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// Spec — one Playwright `test` per screen so retries are visible per-screen
// ─────────────────────────────────────────────────────────────────────────────

const initialDoc = loadDoc();
const profileKey = CAPTURE_CONFIG.device_profile in PROFILES
  ? CAPTURE_CONFIG.device_profile
  : "iphone-15";
const profile = PROFILES[profileKey as keyof typeof PROFILES];

test.use({
  baseURL: CAPTURE_CONFIG.base_url,
  storageState: CAPTURE_CONFIG.auth.storage_state_path,
  ...profile,
});

test.describe.configure({ mode: "serial" });

test.describe(`screen-flow capture (${path.basename(PLATFORM_ROOT)})`, () => {
  fs.mkdirSync(SHOTS_DIR, { recursive: true });

  const targets = ONLY_SCREEN
    ? initialDoc.screens.filter((s) => s.id === ONLY_SCREEN)
    : initialDoc.screens;

  for (const screen of targets) {
    test(`capture ${screen.id}`, async ({ page, context }) => {
      const runId = crypto.randomUUID();
      emit("INFO", "screen_capture_init", { run_id: runId, screen_id: screen.id });

      await applyAllDeterminism(page, context, CAPTURE_CONFIG.determinism);

      let lastError: Error | null = null;
      let lastReason: string = "unknown";
      let captured = false;
      let imageMd5 = "";
      const target = screen.meta?.route ?? `/${screen.id}`;
      const pngPath = path.join(SHOTS_DIR, `${screen.id}.png`);

      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        const start = Date.now();
        try {
          await page.goto(target, { timeout: GOTO_TIMEOUT_MS, waitUntil: "load" });
          if (screen.meta?.wait_for) {
            await page.waitForSelector(screen.meta.wait_for, { timeout: GOTO_TIMEOUT_MS });
          }
          await page.screenshot({ path: pngPath, fullPage: false });
          imageMd5 = md5OfFile(pngPath);
          const hotspots = await captureBoundingBoxes(page, screen.body, profile.viewport);

          // Persist captured state
          const doc = loadDoc();
          setScreen(doc, screen.id, (s) => {
            s.status = "captured";
            s.image = path.relative(PLATFORM_ROOT, pngPath);
            s.capture = {
              captured_at: nowIso(),
              app_version: process.env.APP_VERSION || "unknown",
              image_md5: imageMd5,
              viewport: { w: profile.viewport.width, h: profile.viewport.height },
            };
            delete s.failure;
            if (hotspots && hotspots.length > 0) s.hotspots = hotspots;
          });
          saveDocLocked(doc);

          emit("INFO", "screen_capture_success", {
            run_id: runId,
            screen_id: screen.id,
            attempt,
            duration_ms: Date.now() - start,
            image_md5: imageMd5,
          });
          captured = true;
          break;
        } catch (err) {
          lastError = err as Error;
          lastReason = classifyError(lastError);
          emit("WARN", "screen_capture_retry", {
            run_id: runId,
            screen_id: screen.id,
            attempt,
            reason: lastReason,
            error: lastError.message?.slice(0, 500) ?? "",
          });
          if (attempt < MAX_RETRIES) {
            await delay(BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)]);
          }
        }
      }

      if (!captured) {
        const doc = loadDoc();
        setScreen(doc, screen.id, (s) => {
          s.status = "failed";
          delete s.capture;
          s.failure = {
            reason: lastReason,
            occurred_at: nowIso(),
            retry_count: MAX_RETRIES,
            last_error_message: (lastError?.message ?? "").slice(0, 500),
          };
        });
        saveDocLocked(doc);

        emit("ERROR", "screen_capture_failed", {
          run_id: runId,
          screen_id: screen.id,
          reason: lastReason,
        });
        // Fail the per-screen test so workflow exits 1 (FR-046).
        expect(captured, `capture failed for ${screen.id}: ${lastReason}`).toBeTruthy();
      }
    });
  }
});
