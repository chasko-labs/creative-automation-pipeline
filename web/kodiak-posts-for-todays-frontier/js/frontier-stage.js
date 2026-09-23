// frontier-stage — transparent-canvas Babylon.js stage behind the Kodiak
// frontier web UI. Wired lab-only: index.html imports this module and calls
// mount() beside the existing ?ember3d=1 boot guard. Importing it alone has
// zero effect until mount() is called.
//
// Design rules (all enforced below):
//  1. The ONLY 3D code this module ever loads is the already-vendored entry
//     ../vendor/kodiak-ember.esm.js (built from src/kodiak-ember.js,
//     @babylonjs/core 9.4.1). No new dependencies, no CDN, no remote assets.
//     The import is lazy: it fires inside mount(), after the hard-off gates
//     pass, so reduced-motion / mobile / WebGL-less visits never fetch it.
//     (Note: index.html already loads the same entry as a static module for
//     the lab-only ?ember3d=1 path, so on this page the dynamic import below
//     resolves from the module cache — no second fetch.)
//  2. The engine is the harness singleton (KodiakEmber._harness.ensureEngine,
//     alpha:true). This module NEVER calls runRenderLoop itself — the harness
//     owns the single _masterTick loop, and registerSceneView only attaches
//     views to it. No duplicate loops are possible through this surface.
//  3. The stage canvas is fixed, inset-0, pointer-events:none, aria-hidden,
//     inserted as the first element child of <body> (behind DOM content),
//     opacity 0 until the first successful frame, then faded to 1.
//  4. Hard-off (DOM/CSS fallback left pixel-identical — the canvas is removed
//     or never created) when: prefers-reduced-motion, viewport max-width
//     860px, the vendored module fails to load (e.g. file://), engine
//     creation throws, or the harness exposes no stage factory / the factory
//     throws. The software-renderer refusal (SwiftShader/llvmpipe) stays
//     inside the harness gate (gateReason/canMount3D); this module surfaces
//     its verdict via status().deviceGate but never overrides it.
//  5. Scene content is procedural / clear-color ONLY — this module creates no
//     textures, materials, or asset fetches of any kind. mount() picks up
//     createStageScene via the harness surface (KodiakEmber.createStageScene
//     or _harness.createStageScene, whichever the vendored entry exposes)
//     and registers the returned camera on the stage canvas, so a mounted
//     stage renders the procedural scene instead of staying transparent.
//     registerViewport remains for extra caller-supplied views.

// ---------------------------------------------------------------------------
// INTEGRATION (wired):
//  mount call ..... index.html: mount() runs in a module script AFTER the
//                   static vendor/kodiak-ember.esm.js script, under the same
//                   ?ember3d=1 lab gate as the existing boot guard — the stage
//                   stays lab-gated until the opaque-mask issue noted there
//                   is resolved.
//  scroll bridge .. js/scroll-swap.js (whole file): the window + .wrap scroll
//                   listener pattern; index.html line 124 (.wrap owns desktop
//                   scrolling). A stage parallax offset would subscribe the
//                   same two sources and write only camera/view offsets.
//  view registration  js/preview-parallax.js (hero-tile scope pattern) and
//                   js/recipe-cards.js (card hosts): per-view canvases pass
//                   through registerViewport(viewId, canvas, camera).
//  scene factory .. src/kodiak-ember.js: createStageScene(engine), exported
//                   top-level and on _harness, rebuilt into vendor/ via
//                   `npm run build:ember`. Until the committed bundle carries
//                   it, mount() reports off/no-stage-factory and the fallback
//                   stays pixel-identical.
// ---------------------------------------------------------------------------

const VENDOR_URL = "../vendor/kodiak-ember.esm.js";
// The page's static <script> tag loads the same entry WITH a ?v= cache-bust
// query. A bare-URL dynamic import would fetch a SECOND module instance and
// Babylon throws re-registering its statics ("Cannot redefine property").
// Resolve the vendor URL from the static tag so both sides share one module
// record — no stamp to keep in sync, bump-version can rewrite the tag freely.
function vendorUrl() {
  try {
    const tag = document.querySelector('script[src*="kodiak-ember.esm.js"]');
    const src = tag && tag.getAttribute("src");
    if (src) return new URL(src, document.baseURI).href;
  } catch (_e) {
    // No static tag (or no DOM): fall back to the bare relative URL.
  }
  return VENDOR_URL;
}
const STAGE_ID = "frontier-stage";
const FADE_MS = 600;
const LOW_POWER_QUERY = "(max-width: 860px)";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * @typedef {object} ViewRecord
 * @property {string} viewId
 * @property {HTMLCanvasElement} canvas
 * @property {unknown} camera
 * @property {boolean} firstFrameSeen
 */

/** @type {HTMLCanvasElement | null} */
let stageCanvas = null;
/** @type {unknown} engine from the harness singleton (opaque on purpose) */
let engine = null;
/** @type {{ ensureEngine: Function, registerSceneView: Function, unregisterSceneView: Function, createStageScene?: Function } | null} */
let harness = null;
/** @type {Map<string, ViewRecord>} */
const views = new Map();
/** @type {string | null} last hard-off / failure reason, null when live */
let offReason = null;
/** @type {string | null} harness device-gate verdict code (informational only — never a hard-off) */
let deviceGate = null;
/** viewId under which mount() registers its own procedural stage view */
const STAGE_VIEW_ID = "frontier-stage";

/**
 * Synchronous hard-off check. No DOM is touched and no module is fetched
 * when this returns non-null.
 * @returns {string | null} reason code, or null when the stage may mount.
 */
export function hardOffReason() {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return "no-document";
  }
  try {
    if (
      window.matchMedia &&
      window.matchMedia(REDUCED_MOTION_QUERY).matches
    ) {
      return "reduced-motion";
    }
    if (window.matchMedia && window.matchMedia(LOW_POWER_QUERY).matches) {
      return "low-power-viewport";
    }
  } catch (_e) {
    return "media-query-failed";
  }
  return null;
}

/** Remove the stage canvas if present; fallback renders exactly as before. */
function removeCanvas() {
  if (stageCanvas) {
    stageCanvas.remove();
    stageCanvas = null;
  }
}

/**
 * Mount the transparent stage canvas + shared engine. Idempotent.
 * @returns {Promise<{ status: "on" | "off", reason: string | null }>}
 */
export async function mount() {
  if (engine && stageCanvas) return { status: "on", reason: null };
  const gate = hardOffReason();
  if (gate) {
    offReason = gate;
    return { status: "off", reason: gate };
  }

  const canvas = document.createElement("canvas");
  canvas.id = STAGE_ID;
  canvas.setAttribute("aria-hidden", "true");
  // Behind DOM content: first child of body + z-index 0, never intercepts input.
  canvas.style.cssText = [
    "position:fixed",
    "inset:0",
    "width:100vw",
    "height:100vh",
    "z-index:0",
    "pointer-events:none",
    "opacity:0",
    `transition:opacity ${FADE_MS}ms ease`,
  ].join(";");
  document.body.insertBefore(canvas, document.body.firstChild);
  stageCanvas = canvas;

  /** @type {{ KodiakEmber?: any } | null} */
  let mod = null;
  try {
    mod = await import(/* @vite-ignore */ vendorUrl());
  } catch (_e) {
    // file:// or any load failure: leave the fallback pixel-identical.
    offReason = "module-load-failed";
    removeCanvas();
    return { status: "off", reason: offReason };
  }
  const ember =
    (mod && mod.KodiakEmber) ||
    (typeof window !== "undefined" ? window.KodiakEmber : null);
  if (!ember || !ember._harness || typeof ember._harness.ensureEngine !== "function") {
    offReason = "harness-unavailable";
    removeCanvas();
    return { status: "off", reason: offReason };
  }
  harness = ember._harness;
  try {
    // Singleton: the harness creates the Engine once (alpha:true) and owns
    // the single _masterTick runRenderLoop. Never call runRenderLoop here.
    engine = harness.ensureEngine();
  } catch (_e) {
    offReason = "webgl-context-failed";
    harness = null;
    removeCanvas();
    return { status: "off", reason: offReason };
  }
  // Pick up the procedural stage scene via the harness surface (top-level
  // export preferred, _harness copy as fallback). Missing factory (e.g. a
  // committed bundle predating it) is a hard-off: canvas removed, fallback
  // pixel-identical.
  const factory =
    (ember && typeof ember.createStageScene === "function" && ember.createStageScene) ||
    (harness && typeof harness.createStageScene === "function" && harness.createStageScene);
  if (!factory) {
    offReason = "no-stage-factory";
    engine = null;
    harness = null;
    removeCanvas();
    return { status: "off", reason: offReason };
  }
  // Surface the harness device-gate verdict for debuggers. Informational
  // ONLY — the harness gate stays authoritative on its own path and this
  // module never overrides it (no extra hard-off here).
  try {
    const verdict =
      ember && typeof ember.gateReason === "function" ? ember.gateReason(canvas) : null;
    deviceGate = verdict && verdict.code ? verdict.code : null;
  } catch (_e) {
    deviceGate = null;
  }
  let stage = null;
  try {
    stage = factory(engine);
  } catch (_e) {
    stage = null;
  }
  if (!stage || !stage.scene || !stage.camera) {
    offReason = "stage-scene-failed";
    engine = null;
    harness = null;
    removeCanvas();
    return { status: "off", reason: offReason };
  }
  // Attach the stage view to the existing harness loop — never start one.
  // First successful frame fades the canvas 0->1; before that it stays
  // transparent (indistinguishable from the fallback).
  const render = () => {
    stage.scene.render();
    const rec = views.get(STAGE_VIEW_ID);
    if (rec && !rec.firstFrameSeen) {
      rec.firstFrameSeen = true;
      canvas.style.opacity = "1";
    }
  };
  // Never take another context mode on this canvas (no getContext anywhere
  // in this module): the engine composites registered views via a 2d
  // drawImage, and any foreign context would void that copy.
  harness.registerSceneView(canvas, stage.camera, render);
  views.set(STAGE_VIEW_ID, {
    viewId: STAGE_VIEW_ID,
    canvas,
    camera: stage.camera,
    firstFrameSeen: false,
  });
  offReason = null;
  return { status: "on", reason: null };
}

/**
 * Register a named viewport on the shared engine. Attaches the view to the
 * existing render loop — never starts one. Idempotent per viewId/canvas.
 * The canvas fades 0->1 only after its first successful frame.
 *
 * @param {string} viewId stable viewport name (e.g. "hero", "card-12")
 * @param {HTMLCanvasElement} canvas view canvas (stage canvas or a card canvas)
 * @param {unknown} camera Babylon camera owning the view's scene; supplied by
 *   the caller (e.g. the mount() stage view uses createStageScene — see header).
 * @param {(...args: any[]) => void} [customRender] optional per-frame hook
 * @returns {{ status: "on" | "off" | "pending", reason: string | null }}
 */
export function registerViewport(viewId, canvas, camera, customRender) {
  if (!viewId || !canvas || !camera) {
    return { status: "off", reason: "bad-args" };
  }
  const existing = views.get(viewId);
  if (existing) return { status: engine ? "on" : "pending", reason: offReason };
  /** @type {ViewRecord} */
  const rec = { viewId, canvas, camera, firstFrameSeen: false };
  views.set(viewId, rec);
  if (!engine || !harness) return { status: "pending", reason: offReason || "not-mounted" };
  const wrapped = (...args) => {
    if (!rec.firstFrameSeen) {
      rec.firstFrameSeen = true;
      // First successful frame only: reveal. Canvas stays transparent before.
      canvas.style.opacity = "1";
    }
    if (typeof customRender === "function") customRender(...args);
  };
  harness.registerSceneView(canvas, camera, wrapped);
  return { status: "on", reason: null };
}

/**
 * Unregister one viewport (stops its rendering, keeps the shared loop).
 * @param {string} viewId
 */
export function unregisterViewport(viewId) {
  const rec = views.get(viewId);
  if (!rec) return;
  views.delete(viewId);
  try {
    if (engine && harness) harness.unregisterSceneView(rec.canvas);
  } catch (_e) {
    // Unregister is best-effort; a torn-down engine is already the goal state.
  }
}

/** Tear down every view + the stage canvas. Engine disposal stays with the harness. */
export function destroy() {
  for (const viewId of Array.from(views.keys())) unregisterViewport(viewId);
  removeCanvas();
  engine = null;
  harness = null;
  offReason = null;
  deviceGate = null;
}

/** Current stage state for debuggers and later boot guards. */
export function status() {
  return {
    mounted: Boolean(engine && stageCanvas),
    offReason,
    deviceGate,
    views: Array.from(views.keys()),
  };
}
