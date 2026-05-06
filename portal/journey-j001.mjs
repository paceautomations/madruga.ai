// Execute Journey J-001 from platforms/madruga-ai/testing/journeys.md
// Steps:
//   1. browser navigate http://localhost:4321 (with screenshot)
//   2. browser assert_contains madruga-ai
//   3. browser assert_contains prosauai
//   4. api GET http://localhost:4321/madruga-ai/business/vision/ → assert_status: 200
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const REPO_ROOT = resolve(process.cwd(), '..');
const OUT_DIR = resolve(
  REPO_ROOT,
  'platforms/madruga-ai/epics/027-screen-flow-canvas/smoke-shots',
);
mkdirSync(OUT_DIR, { recursive: true });

const results = [];
let exitCode = 0;

function record(step, status, detail = '') {
  results.push({ step, status, detail });
  console.log(JSON.stringify({ step, status, detail }));
  if (status !== 'pass') exitCode = 1;
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();

try {
  // Step 1: navigate http://localhost:4321 + screenshot
  const resp = await page.goto('http://localhost:4321', { waitUntil: 'networkidle', timeout: 30000 });
  const status = resp ? resp.status() : 0;
  if (status === 200) {
    await page.screenshot({
      path: `${OUT_DIR}/j001-step1-home.png`,
      fullPage: false,
    });
    record('step1_navigate_home', 'pass', `status=${status}`);
  } else {
    record('step1_navigate_home', 'fail', `status=${status}`);
  }

  // Step 2: assert_contains madruga-ai
  const html = (await page.content()).toLowerCase();
  if (html.includes('madruga-ai') || html.includes('madruga.ai')) {
    record('step2_assert_madruga_ai', 'pass');
  } else {
    record('step2_assert_madruga_ai', 'fail', 'token not found in HTML');
  }

  // Step 3: assert_contains prosauai
  if (html.includes('prosauai')) {
    record('step3_assert_prosauai', 'pass');
  } else {
    record('step3_assert_prosauai', 'fail', 'token not found in HTML');
  }

  // Step 4: api GET vision/ → 200
  const apiResp = await page.request.get('http://localhost:4321/madruga-ai/business/vision/');
  if (apiResp.status() === 200) {
    record('step4_api_vision_200', 'pass', `status=${apiResp.status()}`);
  } else {
    record('step4_api_vision_200', 'fail', `status=${apiResp.status()}`);
  }
} catch (err) {
  record('exception', 'fail', String(err));
}

await ctx.close();
await browser.close();

console.log('---SUMMARY---');
console.log(JSON.stringify({ journey: 'J-001', total: results.length, passed: results.filter((r) => r.status === 'pass').length, failed: results.filter((r) => r.status === 'fail').length }));
process.exit(exitCode);
