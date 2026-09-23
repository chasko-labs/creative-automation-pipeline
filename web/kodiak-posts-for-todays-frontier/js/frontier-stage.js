// frontier-stage — SPIKE, not referenced by any HTML yet.
//
// Transparent-canvas Babylon.js stage behind the Kodiak frontier web UI.
// READ THIS BEFORE WIRING IT UP: this module intentionally does nothing on
// its own. Importing it has zero effect until a later change calls `mount()`
// (and no <script> tag points at it, so today it ships zero bytes to the
// page). It exists so the mount/scroll/view integration can be reviewed
// before any page pays for it.
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
//     860px, the vendored module fails to load (e.g. file://), or engine
//     creation throws. The software-renderer refusal (SwiftShader/llvmpipe)
//     stays inside the harness gate (gateReason/canMount3D); this module
//     surfaces its verdict via status() but never overrides it.
//  5. Scene content is procedural / clear-color ONLY — this module creates no
//     textures, materials, or asset fetches of any kind. LIMITATION (honest):
//     the vendored entry exports only the KodiakEmber facade (mounts + gate +
//     harness internals), NOT the Scene/Camera classes, so a procedural stage
//     scene cannot be constructed from this side of the bundle. registerViewport
//     therefore takes a caller-supplied camera (built by a future harness
//     factory in src/kodiak-ember.js), and mount() without a registered view
//     leaves the canvas transparent — visually identical to the fallback.
//     See INTEGRATION below.

// ---------------------------------------------------------------------------
// INTEGRATION (for the later change — none of this is wired yet):
//  mount call ..... index.html line 113 (</head><body>): insert the
//                   mount() call as a module script AFTER the static
//                   vendor/kodiak-ember.esm.js script (~line 548), beside the
//                   existing ?ember3d=1 boot guard (~lines 549-560), so the
//                   stage stays lab-gated until the opaque-mask issue noted
//                   there is resolved.
//  scroll bridge .. js/scroll-swap.js (whole file): the window + .wrap scroll
//                   listener pattern; index.html line 124 (.wrap owns desktop
//                   scrolling). A stage parallax offset would subscribe the
//                   same two sources and write only camera/view offsets.
//  view registration  js/preview-parallax.js (hero-tile scope pattern) and
//                   js/recipe-cards.js (card hosts): per-view canvases pass
//                   through registerViewport(viewId, canvas, camera).
//  scene factory .. src/kodiak-ember.js export block (~line 1414): add a
//                   createStageScene(engine) harness export; mount() will pick
//                   it up via the _harness surface with zero changes here.
// ---------------------------------------------------------------------------

const VENDOR_URL = "../vendor/kodiak-ember.esm.js";
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
/** @type {{ ensureEngine: Function, registerSceneView: Function, unregisterSceneView: Function } | null} */
let harness = null;
/** @type {Map<string, ViewRecord>} */
const views = new Map();
/** @type {string | null} last hard-off / failure reason, null when live */
let offReason = null;

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
    mod = await import(/* @vite-ignore */ VENDOR_URL);
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
 *   the caller (a future harness scene factory — see header).
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
}

/** Current stage state for debuggers and later boot guards. */
export function status() {
  return {
    mounted: Boolean(engine && stageCanvas),
    offReason,
    views: Array.from(views.keys()),
  };
}
