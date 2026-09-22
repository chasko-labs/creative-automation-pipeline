// Shared helpers for the committed live-browser harness (tests/live).
// Every helper runs against the REAL page: no stubs, no mocks.
import { spawn } from "node:child_process";
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const EXE_CANDIDATES = [
  process.env.HOME + "/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome",
];

export async function launch(videoDir) {
  mkdirSync(videoDir, { recursive: true });
  const common = { args: ["--no-sandbox"] };
  try {
    return await chromium.launch({ ...common, headless: true });
  } catch (e) {
    for (const exe of EXE_CANDIDATES) {
      try {
        return await chromium.launch({ ...common, headless: true, executablePath: exe });
      } catch (_) { /* try next */ }
    }
    throw e;
  }
}

// Serve a static dir on 127.0.0.1; resolves {server, port, baseUrl}. Caller closes.
export function serveStatic(dir, port = 8901) {
  const server = spawn("python3", ["-m", "http.server", String(port), "--directory", dir],
    { stdio: "ignore", detached: true });
  server.unref();
  return { server, port, baseUrl: `http://127.0.0.1:${port}`, stop() { try { process.kill(-server.pid); } catch (_) {} } };
}

export async function passGate(page, password = "cakes") {
  await page.waitForTimeout(1200);
  await page.evaluate((pw) => {
    const input = document.querySelector('input[type="password"], input:not([type])');
    const btn = Array.from(document.querySelectorAll("button")).find((b) => /enter/i.test(b.textContent));
    if (input && btn) { input.value = pw; btn.click(); }
  }, password);
  await page.waitForTimeout(2200); // catalog fetch + restore passes + secondaries
}

// Skip the scenario with an explicit reason (harness reports SKIP, exit stays
// green). For environment-gated scenarios: backend endpoints or backend-driven
// surfaces that a local static server cannot provide.
export function skip(reason) {
  const e = new Error(`SKIP: ${reason}`);
  e.skip = String(reason);
  throw e;
}

export function isLocalBase(baseUrl) {
  return /127\.0\.0\.1|localhost/.test(baseUrl || "");
}

export async function gotoLive(page, baseUrl) {
  if (!baseUrl) throw new Error("gotoLive needs baseUrl");
  await page.goto(baseUrl + "/index.html", { waitUntil: "networkidle", timeout: 30000 });
  await passGate(page);
}

// Full observable state: host boxes, tray chips, snapshot skus, storage keys.
export async function pageState(page) {
  return page.evaluate(() => {
    const boxes = Array.from(document.querySelectorAll(".sku-check")).map((b) => b.value + (b.checked ? "=1" : "=0"));
    const chips = Array.from(document.querySelectorAll(".ff-pending-chip[data-sku]")).map((c) => c.dataset.sku);
    let stored = null;
    try { stored = JSON.parse(localStorage.getItem("kodiak_ff_state_v1") || "null"); } catch (e) { stored = "unparseable"; }
    const keys = [];
    try { for (let i = 0; i < localStorage.length; i++) keys.push(localStorage.key(i)); } catch (e) {}
    return { boxes: boxes.length, checked: boxes.filter((b) => b.endsWith("=1")), chips, skus: stored && stored.skus, keys };
  });
}

export async function searchProducts(page, q) {
  return page.evaluate((query) => {
    const s = document.getElementById("productSearch");
    if (!s) return "NO-SEARCH";
    s.value = query;
    s.dispatchEvent(new Event("input", { bubbles: true }));
    return "searched";
  }, q);
}

export async function checkProductBox(page, value) {
  return page.evaluate((v) => {
    const b = Array.from(document.querySelectorAll(".sku-check")).find((x) => x.value === v);
    if (!b) return "NO-BOX";
    if (!b.checked) { b.checked = true; b.dispatchEvent(new Event("change", { bubbles: true })); }
    return "checked";
  }, value);
}

export async function clickChipX(page, value) {
  return page.evaluate((v) => {
    const chip = document.querySelector('.ff-pending-chip[data-sku="' + v + '"]');
    if (!chip) return "NO-CHIP";
    const btn = chip.querySelector(".ff-pending-remove");
    if (!btn) return "NO-X";
    btn.click();
    return "clicked";
  }, value);
}

export async function clickResetDefaults(page) {
  return page.evaluate(() => {
    const btn = document.getElementById("resetDefaults");
    if (!btn) return "NO-RESET-BTN";
    btn.click();
    return "clicked";
  });
}

export function assert(cond, msg) {
  if (!cond) throw new Error("ASSERT: " + msg);
  console.log("  ok:", msg);
}
