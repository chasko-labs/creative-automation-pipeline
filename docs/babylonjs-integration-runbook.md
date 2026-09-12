# Kodiak Frontier — BabylonJS Integration Runbook (Option C)

> implementation runbook for the creative-automation-pipeline team. build upon / within the Kodiak brand
> already live at kodiak.bryanchasko.com — which is this exact repo (same version stamp
> `0.4.1-28d0c98-20260902`). no new brand vocabulary is introduced; every effect renders in colors already
> shipping on that page. this document is complete enough to implement from directly.
>
> companion docs: `docs/design-system-inventory.md` (element inventory + standards S1-S10),
> `docs/kodiak-shading.json` (tint/shade ladders + WCAG), `docs/kodiak-style-guide.md` (7-part brand).
> reference architecture: `chasko-labs/cloud-del-norte-website/src/lib/` (proven BabylonJS 9.4.1 patterns).

## 0. what this is and why Option C

goal: prove the Kodiak UI can carry light and motion — a taste test of 3D-in-web — without breaking the
offline-first `file://` story, the token-driven design system, or WCAG AA. scoped to three small effects,
each on one element, each with a static fallback that is the default.

**why Option C (esbuild + tree-shaken BabylonJS committed as a static bundle):**

- the repo already has a JS toolchain — `package.json` ships `@pandacss/dev 1.12.0`, `"type": "module"`,
  and Panda build scripts. esbuild is a second devDependency beside Panda, not a toolchain from zero.
- the offline `file://` feature is preserved: the bundle is built locally, committed as a static IIFE
  `.js`, and loaded with a plain `<script src>` — exactly the convention `glimmer-proxy.js` already uses.
  no ESM at runtime, no CORS, works from `file://`.
- CI stays Python-only. the JS token step (`tokens:css`) is already run locally and committed, not in
  local checks. the Babylon bundle follows the same pattern: **build locally, commit the artifact, CI
  (`scripts/hooks/full-check.sh`) never sees Babylon.** this runbook does not touch `scripts/hooks/full-check.sh`.
- rejected alternatives: CDN ESM import (breaks `file://` — CORS + offline), vendored full UMD (~1.4MB min,
  no tree-shaking).

## 1. prerequisites (verified on the build host)

| requirement      | confirmed value                                                       |
| ---------------- | --------------------------------------------------------------------- |
| node / npm       | v24.14.0 / 11.9.0 present                                             |
| existing JS deps | `@pandacss/dev 1.12.0` (devDependency), `"type": "module"`            |
| babylon version  | pin `@babylonjs/core` exact `9.4.1` (matches cloud-del-norte)         |
| bundler          | pin `esbuild` `0.25.9` (any 0.25.x)                                   |
| linter           | biome `2.4.13` (ecosystem standard — NOT eslint; ruff is Python-only) |
| CI               | local checks, `scripts/hooks/full-check.sh`, Python-only, untouched by this work       |

## 2. token reconciliation (do this FIRST — standards S1/S2/S3, decisions D1/D2/D3)

the live pixels at kodiak.bryanchasko.com are the authority. effects must reference tokens, not raw hex, so
the flat UI and the 3D can never drift apart. because the live site IS this repo, the colors it ships are
established brand — reconcile the token layer TO the live render, do not delete established color.

edit `design/tokens/kodiak.json`, then regenerate: `npm run tokens:config && npm run tokens:css`.

| id  | change                                                                                                                                                              | rationale                                                                      |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| D1  | ADOPT `#B51E14` as `kodiak.color.brand.signalRed` (usage: header title block, links, `.btn.orange`)                                                                 | it is live in production — established, not drift; govern it, do not remove it |
| D3  | reconcile inline `#382316` to the token `#3B2316` (or set the token to `#382316` if that is the true live render — verify the deployed pixel, token conforms to it) | retire the `--chocolate` divergence; one bearBrown value                       |
| D2  | delete the duplicated per-file `:root{}` palette in index.html + details.html; consume `styles.css`                                                                 | single source of truth; no per-file palette drift                              |

these are governance calls the product owner signs off before effect work lands. they are not blocked by the
3D work, but doing them first means the effect code references `var(--colors-brand-*)` cleanly.

## 3. file layout added by this work

```
package.json                                    (+1 script, +2 devDependencies)
src/kodiak-ember.js                             (NEW — authored ES module, the effect source)
web/kodiak-posts-for-todays-frontier/
  vendor/kodiak-ember.iife.js                   (NEW — committed build artifact, ~1MB min)
  index.html                                    (+CSS fallbacks, +script tag, +1 wiring line)
```

no rasters are added — all textures are procedural (`RawTexture`), matching the zero-raster kraft precedent
already in `kodiak.json`.

## 4. build wiring

add to `package.json`:

```json
"devDependencies": {
  "@pandacss/dev": "1.12.0",
  "@babylonjs/core": "9.4.1",
  "esbuild": "0.25.9"
},
"scripts": {
  "tokens:config": "uv run python scripts/gen-panda-config.py",
  "tokens:css": "panda cssgen --outfile web/kodiak-posts-for-todays-frontier/design/styles.css",
  "build:ember": "esbuild src/kodiak-ember.js --bundle --format=iife --global-name=KodiakEmberBundle --minify --target=es2019 --legal-comments=none --outfile=web/kodiak-posts-for-todays-frontier/vendor/kodiak-ember.iife.js"
}
```

build sequence (local, before commit):

```bash
npm install                # first time only — pulls babylon + esbuild
npm run build:ember        # produces the committed vendor/ artifact
biome lint src/kodiak-ember.js   # must exit 0
git add src/kodiak-ember.js web/kodiak-posts-for-todays-frontier/vendor/kodiak-ember.iife.js
```

the runtime API is `window.KodiakEmber` (the module self-assigns it; `--global-name` is a harmless wrapper).

## 5. the shared harness (mirror of cloud-del-norte, all hard lessons baked in)

`src/kodiak-ember.js` opens with a shared-engine singleton and a device gate. these are non-negotiable —
they are the lessons cloud-del-norte paid for.

- **one WebGL context.** a single `Engine` renders to a 1px offscreen working canvas and copies into each
  registered view canvas. never `new Engine()` per element (chrome's ~16 context limit; fiona vanished
  under context pressure when scenes each held their own engine).
- **deep imports only** (`@babylonjs/core/Layers/glowLayer`, not the barrel) so esbuild tree-shakes.
- **device gate `canMount3D(host)`** returns false — leaving the CSS fallback as the entire visual — when
  any of: WebGL unavailable, software renderer (SwiftShader/llvmpipe), `prefers-reduced-motion: reduce`,
  or host has zero layout.
- **Page Visibility API** stops the render loop on hidden tabs.
- **deferred registration** via `ResizeObserver` until a canvas has non-zero layout (a zero-size view
  floods `GL_INVALID_FRAMEBUFFER_OPERATION` every tick).
- **context release** on last-view teardown via `WEBGL_lose_context`.

harness source (top of `src/kodiak-ember.js`):

```js
// kodiak-ember — BabylonJS ambient effects for the Kodiak frontier frontend.
// Option C: authored as ES module, bundled by esbuild to IIFE, committed as
// vendor/kodiak-ember.iife.js. Loaded via plain <script> beside glimmer-proxy.js.
// Exposes window.KodiakEmber. No ESM at runtime, no CORS, file:// works.

import "@babylonjs/core/Animations/animatable.js";
import "@babylonjs/core/Particles/particleSystemComponent.js";
import "@babylonjs/core/Engines/Extensions/engine.alpha.js";

import { Animation } from "@babylonjs/core/Animations/animation";
import { EasingFunction, SineEase } from "@babylonjs/core/Animations/easing";
import { FreeCamera } from "@babylonjs/core/Cameras/freeCamera";
import { Engine } from "@babylonjs/core/Engines/engine";
import { GlowLayer } from "@babylonjs/core/Layers/glowLayer";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { PointLight } from "@babylonjs/core/Lights/pointLight";
import { PBRMaterial } from "@babylonjs/core/Materials/PBR/pbrMaterial";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial";
import { Texture } from "@babylonjs/core/Materials/Textures/texture.js";
import { RawTexture } from "@babylonjs/core/Materials/Textures/rawTexture.js";
import { Color3, Color4 } from "@babylonjs/core/Maths/math.color";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder";
import { ParticleSystem } from "@babylonjs/core/Particles/particleSystem";
import { Scene } from "@babylonjs/core/scene";
import { Logger } from "@babylonjs/core/Misc/logger";

Logger.LogLevels = Logger.WarningLogLevel | Logger.ErrorLogLevel;

// fixed brand palette — tokens only. Color3 is 0..1 linear.
function hex(h) {
  return Color3.FromHexString(h);
}
const BLAZE = hex("#E8530E"); // Blaze Orange — 8px bar signature
const AMBER = hex("#FF8A3D"); // Warm Amber Glow
const PEACH = hex("#FFB07A"); // Blaze Peach
const TERRACOTTA = hex("#AA3F0F"); // Ember Terracotta
const BEAR = hex("#3B2316"); // Bear Brown
const PARCHMENT = hex("#FFF8F0"); // Parchment
// Signal Red #B51E14 is a fixed token but unused by these trials — omitted so
// lint stays clean. Reintroduce as hex("#B51E14") if a future effect needs it.

// ── shared engine singleton (babylon-shared-engine.ts adaptation) ──
let _engine = null,
  _workingCanvas = null,
  _docVisHandlerInstalled = false;
const _views = new Map();
const _deferredObservers = new Map();

function _masterTick() {
  const engine = _engine;
  if (!engine?.activeView) return;
  const view = _views.get(engine.activeView.target);
  if (!view || view.paused) return;
  view.customRender();
}
function _onVisChange() {
  if (!_engine) return;
  if (document.hidden) _engine.stopRenderLoop();
  else _engine.runRenderLoop(_masterTick);
}
function ensureEngine() {
  if (_engine) return _engine;
  _workingCanvas = document.createElement("canvas");
  _workingCanvas.width = 1;
  _workingCanvas.height = 1;
  _workingCanvas.style.cssText =
    "position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;pointer-events:none;visibility:hidden;z-index:-9999";
  _workingCanvas.setAttribute("aria-hidden", "true");
  document.body.appendChild(_workingCanvas);
  try {
    _engine = new Engine(_workingCanvas, true, {
      preserveDrawingBuffer: true,
      stencil: true,
      alpha: true,
    });
  } catch (err) {
    _workingCanvas.remove();
    _workingCanvas = null;
    throw err;
  }
  _engine.runRenderLoop(_masterTick);
  if (!_docVisHandlerInstalled) {
    document.addEventListener("visibilitychange", _onVisChange);
    _docVisHandlerInstalled = true;
  }
  return _engine;
}
function registerSceneView(canvas, camera, customRender) {
  const engine = ensureEngine();
  if (_views.has(canvas) || _deferredObservers.has(canvas)) return;
  if (canvas.clientWidth === 0 || canvas.clientHeight === 0) {
    const obs = new ResizeObserver(() => {
      if (canvas.clientWidth > 0 && canvas.clientHeight > 0) {
        obs.disconnect();
        _deferredObservers.delete(canvas);
        engine.registerView(canvas, camera);
        _views.set(canvas, { customRender, paused: false });
      }
    });
    obs.observe(canvas);
    _deferredObservers.set(canvas, obs);
    return;
  }
  engine.registerView(canvas, camera);
  _views.set(canvas, { customRender, paused: false });
}
function unregisterSceneView(canvas) {
  const pending = _deferredObservers.get(canvas);
  if (pending) {
    pending.disconnect();
    _deferredObservers.delete(canvas);
  }
  if (!_engine) return;
  _engine.unRegisterView(canvas);
  _views.delete(canvas);
  if (_views.size === 0) {
    _engine.stopRenderLoop();
    if (_workingCanvas) {
      const gl =
        _workingCanvas.getContext("webgl2") ||
        _workingCanvas.getContext("webgl");
      const lose = gl?.getExtension("WEBGL_lose_context");
      if (lose?.loseContext) lose.loseContext();
    }
    _engine.dispose();
    _engine = null;
    if (_workingCanvas) {
      _workingCanvas.remove();
      _workingCanvas = null;
    }
    if (_docVisHandlerInstalled) {
      document.removeEventListener("visibilitychange", _onVisChange);
      _docVisHandlerInstalled = false;
    }
  }
}

// ── device gate — reduced-motion is a DEFAULT-TO-CSS signal ──
const SOFTWARE_RE = /SwiftShader|llvmpipe|Software|Microsoft Basic Render/i;
function probeWebGL() {
  try {
    const probe = document.createElement("canvas");
    const gl = probe.getContext("webgl2") || probe.getContext("webgl");
    if (!gl) return { available: false, renderer: "" };
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = ext
      ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL))
      : "";
    const lose = gl.getExtension("WEBGL_lose_context");
    if (lose?.loseContext) lose.loseContext();
    return { available: true, renderer };
  } catch {
    return { available: false, renderer: "" };
  }
}
function prefersReducedMotion() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}
function canMount3D(host) {
  if (typeof document === "undefined") return false;
  const probe = probeWebGL();
  if (!probe.available) return false;
  if (SOFTWARE_RE.test(probe.renderer)) return false;
  if (prefersReducedMotion()) return false;
  if (!host || host.clientWidth === 0 || host.clientHeight === 0) return false;
  return true;
}
```

## 6. Trial 1 — Ember Accent Bar

**element:** `.ff-go#generateCampaign` (the Create button — the one CTA already on-token blaze orange).
**effect:** the 8px blaze bar rendered as breathing campfire coals. GlowLayer + a confined ParticleSystem
with fire ramp coloring (peach -> amber -> blaze -> terracotta -> ember-black) plus a slow SineEase
emissive heartbeat (140-frame cycle, the fiona led-blink tempo, ~4.6s at 30fps — a calm heartbeat, not a
strobe).
**featureDemos lineage:** Fireworks / Fountain particle demos + GlowLayer emissive-pulse.

```js
class EmberBar {
  constructor(canvas) {
    this.canvas = canvas;
    this.engine = ensureEngine();
    this.scene = new Scene(this.engine);
    this.scene.clearColor = new Color4(0, 0, 0, 0);
    this.camera = new FreeCamera("emberCam", new Vector3(0, 0, -6), this.scene);
    this.camera.setTarget(Vector3.Zero());
    this.camera.mode = 1; // ORTHOGRAPHIC
    this.camera.orthoLeft = -8;
    this.camera.orthoRight = 8;
    this.camera.orthoTop = 0.5;
    this.camera.orthoBottom = -0.5;
    const hemi = new HemisphericLight(
      "emberHemi",
      new Vector3(0, 1, 0),
      this.scene,
    );
    hemi.intensity = 0.4;
    hemi.diffuse = AMBER;
    hemi.groundColor = TERRACOTTA;
    this.bar = MeshBuilder.CreateBox(
      "emberBar",
      { width: 16, height: 0.16, depth: 0.16 },
      this.scene,
    );
    const mat = new PBRMaterial("emberBarMat", this.scene);
    mat.albedoColor = TERRACOTTA;
    mat.emissiveColor = BLAZE;
    mat.emissiveIntensity = 1.2;
    mat.metallic = 0;
    mat.roughness = 0.7;
    this.bar.material = mat;
    const l = new PointLight("emberLight", new Vector3(0, 0.2, 0), this.scene);
    l.diffuse = BLAZE;
    l.specular = AMBER.scale(0.3);
    l.intensity = 0.6;
    l.range = 4;
    this.attachParticles();
    this.attachGlow();
    this.attachHeartbeat();
    registerSceneView(canvas, this.camera, () => this.scene.render());
  }
  attachParticles() {
    const ps = new ParticleSystem("emberCoals", 220, this.scene);
    ps.particleTexture = flameTexture(this.scene); // procedural, file:// safe
    ps.emitter = new Vector3(0, 0, 0);
    ps.minEmitBox = new Vector3(-7.6, -0.04, 0);
    ps.maxEmitBox = new Vector3(7.6, 0.04, 0);
    ps.addColorGradient(0.0, toColor4(PEACH, 0.0));
    ps.addColorGradient(0.15, toColor4(PEACH, 0.9));
    ps.addColorGradient(0.4, toColor4(AMBER, 1.0));
    ps.addColorGradient(0.7, toColor4(BLAZE, 0.9));
    ps.addColorGradient(0.9, toColor4(TERRACOTTA, 0.5));
    ps.addColorGradient(1.0, toColor4(BEAR, 0.0));
    ps.minSize = 0.05;
    ps.maxSize = 0.16;
    ps.minLifeTime = 0.5;
    ps.maxLifeTime = 1.1;
    ps.emitRate = 120;
    ps.blendMode = ParticleSystem.BLENDMODE_ADD;
    ps.gravity = new Vector3(0, 0.6, 0);
    ps.direction1 = new Vector3(-0.15, 1, 0);
    ps.direction2 = new Vector3(0.15, 1, 0);
    ps.minEmitPower = 0.3;
    ps.maxEmitPower = 0.8;
    ps.updateSpeed = 0.01;
    ps.start();
    this.particles = ps;
  }
  attachGlow() {
    this.glow = new GlowLayer("emberGlow", this.scene, {
      mainTextureSamples: 2,
    });
    this.glow.intensity = 0.7;
  }
  attachHeartbeat() {
    // 140-frame SineEase = fiona led-blink tempo (~4.6s @30fps)
    const fps = 30,
      cycle = 140;
    const ease = new SineEase();
    ease.setEasingMode(EasingFunction.EASINGMODE_EASEINOUT);
    const anim = new Animation(
      "emberPulse",
      "material.emissiveIntensity",
      fps,
      Animation.ANIMATIONTYPE_FLOAT,
      Animation.ANIMATIONLOOPMODE_CYCLE,
    );
    anim.setKeys([
      { frame: 0, value: 1.6 },
      { frame: Math.round(cycle * 0.42), value: 0.55 },
      { frame: Math.round(cycle * 0.7), value: 1.1 },
      { frame: cycle, value: 1.6 },
    ]);
    anim.setEasingFunction(ease);
    this.bar.animations = [anim];
    this.scene.beginAnimation(this.bar, 0, cycle, true);
  }
  resize() {
    this.engine.resize();
  }
  dispose() {
    if (this.particles) this.particles.dispose();
    this.scene.dispose();
    unregisterSceneView(this.canvas);
  }
}
```

**CSS fallback (the default — always in the DOM):**

```css
/* TRIAL 1 fallback — the 8px blaze bar as a static gradient with a gentle
   CSS breathing pulse. This is the brand signature and must never disappear. */
.ff-go {
  position: relative;
  overflow: hidden;
}
.ff-go::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 8px;
  background: linear-gradient(90deg, #ffb07a, #ff8a3d, #e8530e, #aa3f0f);
  background-size: 200% 100%;
}
@media (prefers-reduced-motion: no-preference) {
  .ff-go::after {
    animation: ember-breathe 4.6s ease-in-out infinite;
  }
}
@keyframes ember-breathe {
  0%,
  100% {
    filter: brightness(1);
    background-position: 0% 50%;
  }
  42% {
    filter: brightness(0.7);
    background-position: 60% 50%;
  }
}
```

**degradation:** gate fail / bundle absent / reduced-motion / zero layout -> `EmberBar` never constructs;
the `.ff-go::after` gradient bar remains (solid blaze signature, breathing only when motion allowed).
hidden tab -> Page Visibility stops the loop, CSS bar unaffected.

## 7. Trial 2 — Living Kraft Cards

**element:** `.card` (all card surfaces).
**effect:** the existing kraft gradient given real depth — a normal-mapped plane behind the card content so
the kraft fiber catches a soft warm light that follows the pointer, drifting on a slow lissajous when idle.
low-contrast warm light only; text legibility untouched (light sits behind content at z-index 0).
**normal-map choice:** procedural `RawTexture` (32x32, ~4KB, tiled) generated once at mount. chosen over a
committed PNG to keep `file://` pure (zero fetch) and add no binary raster — matching the zero-raster kraft
precedent already in `kodiak.json`.
**featureDemos lineage:** Bump/Normal mapping material demo + follow-pointer light demo.

```js
class KraftCard {
  constructor(canvas, host) {
    this.canvas = canvas;
    this.host = host;
    this.engine = ensureEngine();
    this.scene = new Scene(this.engine);
    this.scene.clearColor = new Color4(0, 0, 0, 0);
    this.camera = new FreeCamera(
      "kraftCam",
      new Vector3(0, 0, -3.2),
      this.scene,
    );
    this.camera.setTarget(Vector3.Zero());
    const hemi = new HemisphericLight(
      "kraftHemi",
      new Vector3(0, 0, -1),
      this.scene,
    );
    hemi.intensity = 0.55;
    hemi.diffuse = PARCHMENT;
    hemi.groundColor = hex("#EAD9C4");
    this.warm = new PointLight(
      "kraftWarm",
      new Vector3(0, 0, -1.4),
      this.scene,
    );
    this.warm.diffuse = AMBER;
    this.warm.specular = PEACH.scale(0.2);
    this.warm.intensity = 0.45;
    this.warm.range = 4;
    const plane = MeshBuilder.CreatePlane(
      "kraftPlane",
      { width: 6, height: 4 },
      this.scene,
    );
    const mat = new StandardMaterial("kraftMat", this.scene);
    mat.diffuseColor = hex("#F0E4D4"); // kraft surface base token
    mat.specularColor = TERRACOTTA.scale(0.15); // barely-there warm spec
    mat.specularPower = 64;
    const nm = kraftNormalTexture(this.scene);
    nm.uScale = 8;
    nm.vScale = 6;
    mat.bumpTexture = nm;
    plane.material = mat;
    this.plane = plane;
    this.attachPointerDrift();
    registerSceneView(canvas, this.camera, () => this.scene.render());
  }
  attachPointerDrift() {
    this._t = 0;
    this._targetX = 0;
    this._targetY = 0;
    this._onMove = (ev) => {
      const r = this.host.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      const nx = ((ev.clientX - r.left) / r.width) * 2 - 1;
      const ny = ((ev.clientY - r.top) / r.height) * 2 - 1;
      this._targetX = nx * 2.6;
      this._targetY = -ny * 1.6;
      this._lastMove = performance.now();
    };
    this.host.addEventListener("pointermove", this._onMove, { passive: true });
    this.scene.registerBeforeRender(() => {
      this._t += 0.008;
      const idle = !this._lastMove || performance.now() - this._lastMove > 1400;
      if (idle) {
        this._targetX = Math.sin(this._t) * 1.8;
        this._targetY = Math.sin(this._t * 0.6) * 1.0;
      }
      this.warm.position.x += (this._targetX - this.warm.position.x) * 0.06;
      this.warm.position.y += (this._targetY - this.warm.position.y) * 0.06;
    });
  }
  resize() {
    this.engine.resize();
  }
  dispose() {
    if (this._onMove)
      this.host.removeEventListener("pointermove", this._onMove);
    this.scene.dispose();
    unregisterSceneView(this.canvas);
  }
}
```

**CSS fallback:** none required — the existing `--gradients-kraft.surface` token IS the card. the 3D plane
is purely additive sheen behind content.

**degradation:** gate fail / bundle absent -> the existing kraft gradient token is the card, identical text
legibility (3D light is low-contrast warm, behind content). deferred until the card has layout (gated
drawers/panels safe).

## 8. Trial 3 — Finish-Line Bloom

**element:** `#preview` (fires when the preview tiles populate — the tool's core action).
**effect:** a one-shot slow warm bloom sweep across the tiles in blaze/bear tones (~1.5s), then settles and
self-disposes. rewards the single action the whole tool exists to perform.
**trigger:** at the end of the existing `ratios.forEach` render loop, right after the last
`previewEl.appendChild(tile)` (~line 494 of index.html).
**featureDemos lineage:** glow-layer intensity animation + bloom post-process sweep.

```js
class FinishLineBloom {
  constructor(canvas) {
    this.canvas = canvas;
    this.engine = ensureEngine();
    this.scene = new Scene(this.engine);
    this.scene.clearColor = new Color4(0, 0, 0, 0);
    this.camera = new FreeCamera("bloomCam", new Vector3(0, 0, -6), this.scene);
    this.camera.setTarget(Vector3.Zero());
    this.camera.mode = 1; // orthographic
    this.camera.orthoLeft = -8;
    this.camera.orthoRight = 8;
    this.camera.orthoTop = 4.5;
    this.camera.orthoBottom = -4.5;
    const hemi = new HemisphericLight(
      "bloomHemi",
      new Vector3(0, 1, 0),
      this.scene,
    );
    hemi.intensity = 0.5;
    hemi.diffuse = BLAZE;
    hemi.groundColor = BEAR;
    this.sweep = MeshBuilder.CreatePlane(
      "bloomSweep",
      { width: 4, height: 10 },
      this.scene,
    );
    const mat = new PBRMaterial("bloomMat", this.scene);
    mat.albedoColor = BEAR;
    mat.emissiveColor = BLAZE;
    mat.emissiveIntensity = 0;
    mat.alpha = 0;
    mat.metallic = 0;
    mat.roughness = 0.6;
    this.sweep.material = mat;
    this.sweep.position.x = -10;
    this.glow = new GlowLayer("bloomGlow", this.scene, {
      mainTextureSamples: 2,
    });
    this.glow.intensity = 0;
    registerSceneView(canvas, this.camera, () => this.scene.render());
    this._mat = mat;
  }
  fire(reducedMotion) {
    const fps = 30,
      dur = Math.round(fps * 1.5);
    const ease = new SineEase();
    ease.setEasingMode(EasingFunction.EASINGMODE_EASEINOUT);
    if (reducedMotion) {
      // instant settle, no sweep — a brief warm flash then off
      this._mat.emissiveIntensity = 0.6;
      this._mat.alpha = 0.12;
      this.glow.intensity = 0.3;
      const settle = new Animation(
        "bloomSettle",
        "material.emissiveIntensity",
        fps,
        Animation.ANIMATIONTYPE_FLOAT,
        Animation.ANIMATIONLOOPMODE_CONSTANT,
      );
      settle.setKeys([
        { frame: 0, value: 0.6 },
        { frame: Math.round(fps * 0.4), value: 0 },
      ]);
      this.sweep.animations = [settle];
      this.scene.beginAnimation(
        this.sweep,
        0,
        Math.round(fps * 0.4),
        false,
        1,
        () => this.dispose(),
      );
      return;
    }
    const posX = new Animation(
      "bloomPos",
      "position.x",
      fps,
      Animation.ANIMATIONTYPE_FLOAT,
      Animation.ANIMATIONLOOPMODE_CONSTANT,
    );
    posX.setKeys([
      { frame: 0, value: -10 },
      { frame: dur, value: 10 },
    ]);
    posX.setEasingFunction(ease);
    const emis = new Animation(
      "bloomEmis",
      "material.emissiveIntensity",
      fps,
      Animation.ANIMATIONTYPE_FLOAT,
      Animation.ANIMATIONLOOPMODE_CONSTANT,
    );
    emis.setKeys([
      { frame: 0, value: 0 },
      { frame: Math.round(dur * 0.3), value: 1.4 },
      { frame: Math.round(dur * 0.7), value: 1.4 },
      { frame: dur, value: 0 },
    ]);
    const alpha = new Animation(
      "bloomAlpha",
      "material.alpha",
      fps,
      Animation.ANIMATIONTYPE_FLOAT,
      Animation.ANIMATIONLOOPMODE_CONSTANT,
    );
    alpha.setKeys([
      { frame: 0, value: 0 },
      { frame: Math.round(dur * 0.3), value: 0.18 },
      { frame: Math.round(dur * 0.7), value: 0.18 },
      { frame: dur, value: 0 },
    ]);
    this.sweep.animations = [posX, emis, alpha];
    this.scene.beginAnimation(this.sweep, 0, dur, false, 1, () =>
      this.dispose(),
    );
  }
  resize() {
    this.engine.resize();
  }
  dispose() {
    this.scene.dispose();
    unregisterSceneView(this.canvas);
  }
}
```

**CSS fallback:**

```css
/* TRIAL 3 fallback — a one-shot CSS warm flash on the preview region when a
   .is-fresh class is added by index.html. Instant/no-sweep under reduced motion. */
#preview.is-fresh {
  animation: finish-flash 1.5s ease-out 1;
}
@keyframes finish-flash {
  0% {
    box-shadow: 0 0 0 0 rgba(232, 83, 14, 0);
  }
  30% {
    box-shadow: 0 0 32px 4px rgba(232, 83, 14, 0.18);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(232, 83, 14, 0);
  }
}
@media (prefers-reduced-motion: reduce) {
  #preview.is-fresh {
    animation: none;
  }
}
```

**degradation:** reduced-motion -> instant warm flash settle, no positional sweep. no WebGL / bundle absent
-> CSS box-shadow flash only. self-disposes on animation-end so no lingering context.

## 9. procedural textures + public API (bottom of `src/kodiak-ember.js`)

```js
function flameTexture(scene) {
  // 8x8 soft radial dot, additive — no PNG asset
  const size = 8,
    data = new Uint8Array(size * size * 4),
    c = (size - 1) / 2;
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const dx = (x - c) / c,
        dy = (y - c) / c;
      const d = Math.min(1, Math.sqrt(dx * dx + dy * dy)),
        a = Math.max(0, 1 - d);
      const i = (y * size + x) * 4;
      data[i] = 255;
      data[i + 1] = 255;
      data[i + 2] = 255;
      data[i + 3] = Math.round(a * a * 255);
    }
  const tex = RawTexture.CreateRGBATexture(
    data,
    size,
    size,
    scene,
    false,
    false,
    Texture.BILINEAR_SAMPLINGMODE,
  );
  tex.hasAlpha = true;
  return tex;
}
function kraftNormalTexture(scene) {
  // 32x32 tangent-space normal, crossed fiber
  const size = 32,
    data = new Uint8Array(size * size * 4);
  const h = (x, y) => {
    const a = Math.sin((x * 0.9 + y * 0.9) * 1.3);
    const b = Math.sin((x * 0.9 - y * 0.9) * 1.7);
    const g = Math.sin(x * 5.1) * Math.cos(y * 4.7) * 0.25;
    return (a * 0.5 + b * 0.35 + g) * 0.5;
  };
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const hL = h((x - 1 + size) % size, y),
        hR = h((x + 1) % size, y);
      const hD = h(x, (y - 1 + size) % size),
        hU = h(x, (y + 1) % size);
      const strength = 1.4,
        nx = (hL - hR) * strength,
        ny = (hD - hU) * strength,
        nz = 1;
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1,
        i = (y * size + x) * 4;
      data[i] = Math.round(((nx / len) * 0.5 + 0.5) * 255);
      data[i + 1] = Math.round(((ny / len) * 0.5 + 0.5) * 255);
      data[i + 2] = Math.round(((nz / len) * 0.5 + 0.5) * 255);
      data[i + 3] = 255;
    }
  const tex = RawTexture.CreateRGBATexture(
    data,
    size,
    size,
    scene,
    true,
    false,
    Texture.TRILINEAR_SAMPLINGMODE,
  );
  tex.wrapU = Texture.WRAP_ADDRESSMODE;
  tex.wrapV = Texture.WRAP_ADDRESSMODE;
  return tex;
}
function toColor4(c3, a) {
  return new Color4(c3.r, c3.g, c3.b, a);
}

function overlayCanvas(host) {
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  canvas.style.cssText =
    "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;display:block";
  if (getComputedStyle(host).position === "static")
    host.style.position = "relative";
  host.appendChild(canvas);
  return canvas;
}
function mountEmberBar(selector) {
  const btn = document.querySelector(selector || ".ff-go#generateCampaign");
  if (!btn || !canMount3D(btn)) return null;
  const canvas = overlayCanvas(btn);
  try {
    return new EmberBar(canvas);
  } catch {
    canvas.remove();
    return null;
  }
}
function mountKraftCards(selector) {
  const cards = document.querySelectorAll(selector || ".card"),
    scenes = [];
  cards.forEach((card) => {
    if (!canMount3D(card)) return;
    const canvas = overlayCanvas(card);
    canvas.style.zIndex = "0"; // behind content
    try {
      scenes.push(new KraftCard(canvas, card));
    } catch {
      canvas.remove();
    }
  });
  return scenes;
}
function finishLineBloom(selector) {
  // called after preview render completes
  const host = document.querySelector(selector || "#preview");
  const reduced = prefersReducedMotion();
  if (!host || host.clientWidth === 0 || host.clientHeight === 0) return null;
  const probe = probeWebGL();
  if (!probe.available || SOFTWARE_RE.test(probe.renderer)) return null; // reduced path still allowed
  const canvas = overlayCanvas(host);
  try {
    const b = new FinishLineBloom(canvas);
    b.fire(reduced);
    return b;
  } catch {
    canvas.remove();
    return null;
  }
}
const KodiakEmber = {
  mountEmberBar,
  mountKraftCards,
  finishLineBloom,
  canMount3D,
  _version: "0.1.0",
};
if (typeof window !== "undefined") window.KodiakEmber = KodiakEmber;
export { KodiakEmber };
```

## 10. index.html wiring

script tags — add AFTER the existing `glimmer-proxy.js`:

```html
<script src="vendor/kodiak-ember.iife.js"></script>
<script>
  (function () {
    if (!window.KodiakEmber) return; // bundle missing / blocked -> CSS defaults stand
    function boot() {
      window.KodiakEmber.mountEmberBar(); // .ff-go#generateCampaign
      window.KodiakEmber.mountKraftCards(); // all .card surfaces
    }
    if (document.readyState === "loading")
      document.addEventListener("DOMContentLoaded", boot);
    else boot();
  })();
</script>
```

Trial 3 — one block at the END of the existing preview render (`ratios.forEach`, ~line 494):

```js
  }); // end ratios.forEach
  // finish-line bloom — CSS fallback flash + optional 3D sweep
  previewEl.classList.remove("is-fresh"); void previewEl.offsetWidth; // restart CSS anim
  previewEl.classList.add("is-fresh");
  if (window.KodiakEmber) window.KodiakEmber.finishLineBloom("#preview");
```

## 11. performance budgets + acceptance criteria

| axis           | budget / gate                                                                                           |
| -------------- | ------------------------------------------------------------------------------------------------------- |
| WebGL contexts | exactly 1 (shared engine). verify `chrome://gpu` or `_debugGetViewCount`                                |
| bundle size    | committed artifact ~950KB-1.15MB min / ~260-320KB gzipped (PBR path). record actual after `build:ember` |
| frame rate     | >= 30 FPS with all three effects mounted on a mid-tier laptop iGPU                                      |
| offline        | opens from `file://` with bundle present AND with bundle absent (CSS default)                           |
| reduced-motion | `prefers-reduced-motion: reduce` -> no 3D mounts, CSS is static, bloom instant-settles                  |
| WCAG           | text contrast unchanged vs current (bearBrown on kraft 10.2:1); 3D never sits over text                 |
| lint           | `biome lint src/kodiak-ember.js` exit 0                                                                 |
| pytest         | `uv run --with pytest pytest -x -q` still passes (Python untouched)                                     |
| token fidelity | every effect color resolves to an established brand token (no invented hex)                             |

per-trial acceptance:

- **T1 ember bar** — coals read as warm campfire on `.ff-go`; heartbeat is a slow breathe, not a strobe;
  gate-off shows the CSS gradient bar; hidden tab pauses the loop.
- **T2 kraft cards** — kraft fiber catches light that follows the pointer and drifts when idle; card text
  is exactly as legible as today; gate-off is the existing kraft gradient, visually unchanged.
- **T3 finish bloom** — a single warm sweep fires when preview tiles populate, then self-disposes (no
  lingering context); reduced-motion shows an instant warm flash; no-WebGL shows the CSS box-shadow flash.

## 12. rollout order (definition of done per stage)

1. **token reconciliation** (section 2) — D1/D2/D3 land, `tokens:css` regenerated, PR reviewed. done when
   the inline `:root{}` palettes are gone and effects can reference `var(--colors-brand-*)`.
2. **CSS fallbacks only** (sections 6-8 CSS blocks) — ship the ember bar / finish flash with zero
   BabylonJS. done when the taste test is visible on the live site with no bundle. this is the safe,
   reversible first cut.
3. **Trial 1 3D** — add `src/kodiak-ember.js` + `build:ember` + vendor artifact + ember-bar mount. done
   when acceptance T1 passes and offline/reduced-motion fallbacks verified.
4. **Trials 2 + 3 3D** — enable kraft cards + finish bloom. done when acceptance T2/T3 pass and the FPS +
   single-context budgets hold with all three mounted.
5. **scorecard axis** — add a "3D Progressive Enhancement" axis to the details.html scorecard grid
   (per inventory S9) so the self-audit tracks it: gate present, single context, CSS fallback intact,
   reduced-motion honored.

## 13. known follow-ups (flagged, not in scope)

- **StandardMaterial variant.** dropping `PBRMaterial` for `StandardMaterial`+emissive across all three
  trials cuts the bundle to ~600-700KB min / ~180-210KB gz. viable optimization once the PBR look is
  approved as the target; run as a follow-up trial, measure the visual delta.
- **manualChunks equivalent.** cloud-del-norte splits Babylon into named chunks (meshes/materials/engine/
  shaders/animations). the single-IIFE approach here is correct for one small module; if the effect set
  grows, revisit code-splitting.
- **eslint flat-config gate.** if the team prefers eslint over biome for JS, add `eslint.config.mjs` per
  the haunting JS-lint standard. current ecosystem standard is biome 2.4.13.

---

## 14. Feature-Demo Candidate Catalog (kraft/matte/spot-gloss)

> mined from babylonjs.com/featureDemos against the brand target: matte 20pt URB kraft
> paperboard, printed under matte acrylic with selective UV spot-gloss that catches light.
> every candidate below stays inside Option C — deep tree-shakeable imports only, procedural
> textures (zero rasters), file:// safe. colors reference established `kodiak.json` tokens; no
> invented hex. ambient only — 1-2% presence behind fonts/cards, never over the hand-illustrated
> bear or the generated creative. this catalog extends Trials 1-3; it does not replace them.

### 14.1 the physical translation

the Kodiak box is matte uncoated fiber (high roughness, low specular, warm brown) with hand-illustrated
graphics popping under a thin matte-acrylic coat, and UV spot-gloss that catches a hard highlight where
the light rakes across it. BabylonJS models this exactly with two PBRMaterial sub-features already reachable
from the bundle we ship:

- **matte fiber** = `roughness` high (0.8-0.95) + `sheen` (soft retroreflective fiber glow, the way light
  wraps the raised fibers of uncoated board)
- **selective UV spot-gloss** = `clearCoat` (a thin glossy layer over the matte base — `clearCoat.roughness`
  low, ~0.1-0.2 — that catches a sharp specular the matte base cannot). this is the single closest
  digital analog to UV spot-coating in the entire engine.

both are plugin-configs on the `PBRMaterial` the existing trials already import. that is the headline
tree-shake result: **the tactile paperboard look adds ~0 KB** because PBR is already paid for.

### 14.2 candidate matrix

| candidate                                   | source featureDemo                          | babylon feature                                              | brand-feel payoff                                                                                  | tree-shake weight                                                                     | complexity | verdict                                                                                                                      |
| ------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------- |
| C1 matte+coat paperboard material           | PBR Material Showcase / "Clear coat" demo   | `PBRMaterial.clearCoat` + `.sheen` (plugin configs)          | matte URB base with a UV-spot-gloss highlight that rakes with light — the literal box feel         | ~0 KB added (PBR already bundled; sub-features are config, plugins compile on demand) | low-med    | **RECOMMEND — Trial 4**                                                                                                      |
| C2 procedural kraft fiber via Node Material | Node Material Editor demos (procedural NME) | `NodeMaterial` compiled to a shader, fed noise               | infinite-resolution fiber grain, no raster, tunable in NME then frozen to JSON                     | +80-140 KB min (`Materials/Node/*` + block set)                                       | high       | DEFER — heavier than the RawTexture normal-map already in Trial 2; revisit only if fiber must animate                        |
| C3 detail-map micro-fiber overlay           | "Detail map" material demo                  | `PBRMaterial.detailMap` (albedo+bump+roughness detail layer) | second finer fiber octave over the base normal — closes the "too clean" gap on large card surfaces | ~0 KB added (detailMap is a PBR plugin config) BUT +1 RawTexture per material         | low        | RECOMMEND as a **Trial 4 sub-option** (fold into C1, not its own trial)                                                      |
| C4 spot-gloss sweep highlight               | "Reflection probe" / raking-light demos     | animated `PointLight` position over clearCoat surface        | the highlight travels across the gloss when the pointer moves — spot-coat catching a turning box   | ~0 KB (light + animation already imported)                                            | low        | **RECOMMEND — folds into Trial 4**                                                                                           |
| C5 warm sheen rim on cards                  | PBR `sheen` showcase                        | `PBRMaterial.sheen.isEnabled` + `sheen.color`                | soft warm fiber halo at grazing angle — makes flat cards read as raised paper stock                | ~0 KB added                                                                           | low        | **RECOMMEND — Trial 5**                                                                                                      |
| C6 thin-instance fiber flecks               | "Thin instances" demo                       | `mesh.thinInstanceSetBuffer`                                 | thousands of tiny kraft flecks/specks for tactile grain, one draw call                             | +15-25 KB min (`Meshes/thinInstance*`)                                                | med        | DEFER — pretty, but it is decoration over the bear/creative; risks the "competing with content" rule                         |
| C7 anisotropic paper grain                  | PBR `anisotropy` showcase                   | `PBRMaterial.anisotropy`                                     | directional brushed sheen along the fiber run                                                      | ~0 KB added                                                                           | med        | DEFER — reads more as brushed metal than paper; wrong material story                                                         |
| C8 SSAO2 contact shadow                     | "SSAO2" post-process demo                   | `SSAO2RenderingPipeline`                                     | soft ambient occlusion in the card fiber valleys                                                   | +40-70 KB min (post-process pipeline) AND a second render target                      | med-high   | DEFER — **blows section 11**: extra RT + full-screen pass threatens the >=30fps iGPU budget with multiple card views mounted |
| C9 lens/bloom spot-gloss glint              | "Default rendering pipeline / bloom" demo   | `DefaultRenderingPipeline.bloom`                             | blooms the gloss catch into a soft glint                                                           | +50-90 KB min (default pipeline)                                                      | med        | DEFER — Trial 1 already gets warm glow from `GlowLayer` at far lower weight; bloom pipeline is redundant here                |

### 14.3 what to build vs what to shelve

- build now: **C1 (matte+coat) as Trial 4**, absorbing C3 (detail-map second octave) and C4 (raking
  highlight) as sub-options, and **C5 (sheen rim) as Trial 5**. all three headline picks add ~0 KB because
  they are PBRMaterial plugin configs on a material class already in the bundle. this is the whole reason
  they win: maximum tactile payoff, zero budget cost.
- shelve: C2/C6/C7/C8/C9 each add real weight or a second render pass. none clears the bar of "1-2% ambient
  behind content" strongly enough to justify the KB or the frame cost. C8 (SSAO2) is the explicit
  section-11 hazard — do not ship it without a dedicated FPS trial on the mid-tier iGPU target.

---

## 15. Trial 4 — Matte Paperboard Card (URB base + UV spot-gloss coat)

**element:** `.card` surfaces (same host as Trial 2; Trial 4 is the material upgrade path for the kraft
plane — it can replace the Trial 2 `StandardMaterial` plane or run as the approved-look successor once the
PBR paperboard is signed off).
**effect:** the card-backing plane becomes matte uncoated kraft board (high roughness + warm sheen) wearing
a thin `clearCoat` gloss layer. a warm `PointLight` rakes across it following the pointer (idle lissajous,
reusing Trial 2's drift), so a sharp spot-gloss highlight travels the surface exactly like light turning
across UV spot-coating on the real box. a `detailMap` adds a finer second fiber octave so large cards never
read "too clean." low-contrast, behind content at z-index 0 — text legibility untouched.
**featureDemos lineage:** PBR "Clear coat" showcase + "Detail map" material demo + raking-light /
reflection-probe demos.
**token note (flag for owner):** the coat specular catch tints to parchment `neutral.50` #FFF8F0; the warm
sheen tints to `brand.blazeOrange` #E8530E (same warm bloom already shipping in
`gradient.kraft.surfaceHover`). no new hex. if you want these named, add `kodiak.material.spotGloss.tint`
-> {neutral.50} and `kodiak.material.sheen.warm` -> {brand.blazeOrange} — optional, a token-governance call
in the D1/D2/D3 class.

**worked import list** (add to the existing `src/kodiak-ember.js` import block — all deep, all
tree-shakeable; PBRMaterial + Texture/RawTexture are ALREADY imported by Trials 1-3, so the net new lines
are only the two plugin side-effect registrations):

```js
// Trial 4 — matte paperboard + clearCoat spot-gloss.
// PBRMaterial, RawTexture, Texture, PointLight, Animation, Color3, Vector3,
// MeshBuilder, Scene, FreeCamera, HemisphericLight are ALREADY imported (Trials 1-3).
// clearCoat + detailMap are plugin configs on PBRMaterial; the plugin code compiles
// on first use. No barrel import — esbuild keeps the tree shaken.
import "@babylonjs/core/Materials/PBR/pbrClearCoatConfiguration.js"; // registers clearCoat
import "@babylonjs/core/Materials/material.detailMapConfiguration.js"; // registers detailMap
```

**material + texture setup** (add a `PaperboardCard` class beside `KraftCard`; reuses the harness singleton,
the device gate, and the `attachPointerDrift` pattern verbatim):

```js
class PaperboardCard {
  constructor(canvas, host) {
    this.canvas = canvas;
    this.host = host;
    this.engine = ensureEngine();
    this.scene = new Scene(this.engine);
    this.scene.clearColor = new Color4(0, 0, 0, 0);
    this.camera = new FreeCamera(
      "boardCam",
      new Vector3(0, 0, -3.2),
      this.scene,
    );
    this.camera.setTarget(Vector3.Zero());
    const hemi = new HemisphericLight(
      "boardHemi",
      new Vector3(0, 0, -1),
      this.scene,
    );
    hemi.intensity = 0.5;
    hemi.diffuse = PARCHMENT;
    hemi.groundColor = hex("#EAD9C4"); // kraft-tan token
    // raking warm light — the spot-gloss catcher (C4)
    this.rake = new PointLight(
      "boardRake",
      new Vector3(0, 0, -1.4),
      this.scene,
    );
    this.rake.diffuse = AMBER;
    this.rake.specular = PARCHMENT; // #FFF8F0 gloss catch
    this.rake.intensity = 0.5;
    this.rake.range = 4;

    const plane = MeshBuilder.CreatePlane(
      "boardPlane",
      { width: 6, height: 4 },
      this.scene,
    );
    const mat = new PBRMaterial("boardMat", this.scene);
    // ── matte uncoated URB base ──
    mat.albedoColor = hex("#F0E4D4"); // kraft surface base token (gradient.kraft.surface base)
    mat.metallic = 0; // paper is never metal
    mat.roughness = 0.9; // matte fiber — the uncoated board
    // ── warm fiber sheen (C5 core; the raised-fiber glow) ──
    mat.sheen.isEnabled = true;
    mat.sheen.intensity = 0.35;
    mat.sheen.color = BLAZE.scale(0.5); // warm, derived from blazeOrange token; subtle
    // ── UV spot-gloss coat (C1 headline — matte base, glossy coat) ──
    mat.clearCoat.isEnabled = true;
    mat.clearCoat.intensity = 0.6; // partial coat, like selective spot-coating
    mat.clearCoat.roughness = 0.12; // sharp gloss the matte base can't produce
    // ── base fiber normal (reuse Trial 2's procedural kraft normal) ──
    const baseNormal = kraftNormalTexture(this.scene);
    baseNormal.uScale = 8;
    baseNormal.vScale = 6;
    mat.bumpTexture = baseNormal;
    // ── detailMap: finer second fiber octave (C3) ──
    mat.detailMap.isEnabled = true;
    mat.detailMap.texture = kraftDetailTexture(this.scene); // procedural, RawTexture, file:// safe
    mat.detailMap.bumpLevel = 0.6; // fine grain on top of the base weave
    mat.detailMap.roughnessBlendLevel = 0.3; // vary matte-ness across the fiber
    mat.detailMap.diffuseBlendLevel = 0.08; // barely-there tonal fleck (1-2% rule)

    plane.material = mat;
    this.plane = plane;
    this._mat = mat;
    this.attachPointerDrift(); // identical to Trial 2 — rakes this.rake instead of this.warm
    registerSceneView(canvas, this.camera, () => this.scene.render());
  }
  // attachPointerDrift: copy Trial 2 verbatim, renaming this.warm -> this.rake.
  resize() {
    this.engine.resize();
  }
  dispose() {
    if (this._onMove)
      this.host.removeEventListener("pointermove", this._onMove);
    this.scene.dispose();
    unregisterSceneView(this.canvas);
  }
}
```

**new procedural texture** (add beside `kraftNormalTexture` in section 9 — a finer-frequency variant, same
RawTexture / zero-raster / file:// approach):

```js
function kraftDetailTexture(scene) {
  // 32x32 fine second-octave fiber, RG=normal, B=roughness, A=albedo detail
  const size = 32,
    data = new Uint8Array(size * size * 4);
  const h = (x, y) =>
    Math.sin(x * 11.3) * Math.cos(y * 9.7) * 0.5 +
    Math.sin((x + y) * 6.1) * 0.3;
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const hL = h((x - 1 + size) % size, y),
        hR = h((x + 1) % size, y);
      const hD = h(x, (y - 1 + size) % size),
        hU = h(x, (y + 1) % size);
      const nx = (hL - hR) * 1.2,
        ny = (hD - hU) * 1.2,
        nz = 1;
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1,
        i = (y * size + x) * 4;
      data[i] = Math.round(((nx / len) * 0.5 + 0.5) * 255); // R normal x
      data[i + 1] = Math.round(((ny / len) * 0.5 + 0.5) * 255); // G normal y
      data[i + 2] = Math.round(120 + h(x, y) * 40); // B roughness variance
      data[i + 3] = Math.round(128 + h(x, y) * 24); // A albedo detail (subtle)
    }
  const tex = RawTexture.CreateRGBATexture(
    data,
    size,
    size,
    scene,
    true,
    false,
    Texture.TRILINEAR_SAMPLINGMODE,
  );
  tex.wrapU = Texture.WRAP_ADDRESSMODE;
  tex.wrapV = Texture.WRAP_ADDRESSMODE;
  tex.uScale = 16;
  tex.vScale = 12;
  return tex;
}
```

**CSS fallback:** none new required — the existing `gradient.kraft.surface` token IS the card; Trial 4 is
purely additive matte-coat sheen behind content, same as Trial 2.

**acceptance criteria (T4):**

- card backing reads as matte uncoated kraft board, not flat parchment or glossy plastic — roughness reads
  high everywhere except where the raking light crosses the coat
- a sharp spot-gloss highlight travels the surface as the pointer moves and drifts on the idle lissajous;
  the highlight is the clearCoat catching light, visibly sharper than the matte base
- card text is exactly as legible as today (bearBrown on kraft 10.2:1 unchanged; 3D behind content, z-index 0)
- every color resolves to an established token (albedo #F0E4D4, sheen from blazeOrange, gloss catch parchment) — no invented hex
- gate-off / bundle-absent / reduced-motion -> the existing kraft gradient token is the card, visually unchanged
- single WebGL context preserved (shares the engine singleton); `biome lint` exit 0; pytest untouched
- bundle delta after `build:ember` is < 10 KB min vs the Trial 1-3 baseline (record actual — clearCoat +
  detailMap + sheen are plugin configs, expected near-zero)

---

## 16. Trial 5 — Warm Sheen Rim (matte fiber halo behind fonts/cards)

**element:** the section headers / card title band — the ambient layer directly behind display type
(target: the header title block, mounted as a low-z backing plane behind the text, never over it).
**effect:** a matte plane with `sheen` only (no coat, no particles) that produces a soft warm retroreflective
halo at grazing angles — the way light wraps the raised fibers of uncoated board and gives it that
"warm paper glows slightly at the edge" quality. this is the lightest-touch tactile cue in the catalog:
pure material, one plane, no animation beyond a very slow ambient light breathe. sits at 1-2% presence
behind fonts.
**featureDemos lineage:** PBR `sheen` showcase.

**worked import list** (net new lines: none — everything is already imported by Trials 1-4; sheen is a
config on PBRMaterial):

```js
// Trial 5 — warm sheen rim. Zero new imports.
// PBRMaterial, HemisphericLight, Animation, SineEase, Color3/4, Vector3,
// MeshBuilder, Scene, FreeCamera all already imported by Trials 1-4.
```

**material setup** (add a `SheenRim` class; the smallest class in the module):

```js
class SheenRim {
  constructor(canvas, host) {
    this.canvas = canvas;
    this.host = host;
    this.engine = ensureEngine();
    this.scene = new Scene(this.engine);
    this.scene.clearColor = new Color4(0, 0, 0, 0);
    this.camera = new FreeCamera("sheenCam", new Vector3(0, 0, -3), this.scene);
    this.camera.setTarget(Vector3.Zero());
    this.hemi = new HemisphericLight(
      "sheenHemi",
      new Vector3(0, 0, -1),
      this.scene,
    );
    this.hemi.intensity = 0.45;
    this.hemi.diffuse = PARCHMENT;
    this.hemi.groundColor = hex("#EAD9C4");
    const plane = MeshBuilder.CreatePlane(
      "sheenPlane",
      { width: 8, height: 3 },
      this.scene,
    );
    const mat = new PBRMaterial("sheenMat", this.scene);
    mat.albedoColor = hex("#F4EDE6"); // oatmeal neutral.100 token — card/kraft bag
    mat.metallic = 0;
    mat.roughness = 0.95; // as matte as the engine goes
    mat.sheen.isEnabled = true;
    mat.sheen.intensity = 0.4;
    mat.sheen.color = BLAZE.scale(0.45); // warm halo, derived from blazeOrange token
    mat.sheen.roughness = 0.5; // soft, wide halo — not a hard glint
    const nm = kraftNormalTexture(this.scene);
    nm.uScale = 10;
    nm.vScale = 4;
    mat.bumpTexture = nm;
    plane.material = mat;
    this.plane = plane;
    this.attachBreathe(); // very slow ambient light breathe, fiona tempo
    registerSceneView(canvas, this.camera, () => this.scene.render());
  }
  attachBreathe() {
    // reuse Trial 1's 140-frame SineEase tempo on light intensity
    const fps = 30,
      cycle = 140;
    const ease = new SineEase();
    ease.setEasingMode(EasingFunction.EASINGMODE_EASEINOUT);
    const anim = new Animation(
      "sheenBreathe",
      "intensity",
      fps,
      Animation.ANIMATIONTYPE_FLOAT,
      Animation.ANIMATIONLOOPMODE_CYCLE,
    );
    anim.setKeys([
      { frame: 0, value: 0.45 },
      { frame: Math.round(cycle * 0.5), value: 0.55 },
      { frame: cycle, value: 0.45 },
    ]);
    anim.setEasingFunction(ease);
    this.hemi.animations = [anim];
    this.scene.beginAnimation(this.hemi, 0, cycle, true);
  }
  resize() {
    this.engine.resize();
  }
  dispose() {
    this.scene.dispose();
    unregisterSceneView(this.canvas);
  }
}
```

**CSS fallback:** a static warm inner glow on the header band, motion-gated (matches the Trial 1 fallback
idiom):

```css
/* TRIAL 5 fallback — warm matte-paper sheen behind the header band. Static
   warm inner glow; the breathe only runs when motion is allowed. Behind text. */
.header-title-block {
  position: relative;
}
.header-title-block::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: radial-gradient(
    120% 80% at 50% 100%,
    rgba(232, 83, 14, 0.06) 0%,
    rgba(232, 83, 14, 0) 60%
  ); /* blazeOrange token, 6% */
}
.header-title-block > * {
  position: relative;
  z-index: 1;
} /* text always above */
@media (prefers-reduced-motion: no-preference) {
  .header-title-block::before {
    animation: sheen-breathe 4.6s ease-in-out infinite;
  }
}
@keyframes sheen-breathe {
  0%,
  100% {
    opacity: 0.85;
  }
  50% {
    opacity: 1;
  }
}
```

**acceptance criteria (T5):**

- a soft warm halo reads at the grazing edge of the header backing plane — matte paper that glows faintly,
  not a shiny surface
- presence is 1-2% ambient — the halo never competes with the display type; text sits above at z-index 1 and
  is exactly as legible as today
- breathe is a slow calm heartbeat (140-frame SineEase, ~4.6s), matched to the fiona tempo already used in Trial 1
- colors resolve to tokens only (albedo oatmeal #F4EDE6, halo from blazeOrange) — no invented hex
- gate-off / reduced-motion / bundle-absent -> the CSS radial-glow fallback stands, static, behind text
- single WebGL context preserved; `biome lint` exit 0; pytest untouched
- bundle delta after `build:ember`: ~0 KB (sheen is a config; no new imports)

---

**catalog summary for section 11 update:** Trials 4 and 5 add no meaningful bundle weight (clearCoat, sheen,
detailMap are PBRMaterial plugin configs on a class already bundled; expected < 10 KB min combined delta —
record actual). they share the single engine context. the only section-11 hazards in the mined catalog are
the DEFERRED candidates C8 (SSAO2, second render target) and C9 (bloom pipeline) — neither is recommended.

---

sources: reference architecture `chasko-labs/cloud-del-norte-website/src/lib/` (babylon-shared-engine.ts,
cdn-star-logo/StarScene.ts, babylon-loader.ts, vite.config.ts manualChunks); brand `design/tokens/kodiak.json`

- `docs/kodiak-shading.json`; element inventory `docs/design-system-inventory.md`. featureDemos lineage from
  babylonjs.com/featureDemos as noted per trial.
