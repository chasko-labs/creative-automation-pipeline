// kodiak-ember — BabylonJS ambient effects for the Kodiak frontier frontend.
// Option C: authored as ES module, bundled by esbuild to IIFE, committed as
// vendor/kodiak-ember.iife.js. Loaded via plain <script> beside glimmer-proxy.js.
// Exposes window.KodiakEmber. No ESM at runtime, no CORS, file:// works.
//
// WAVE 0: the shared-engine singleton + device gate + brand palette.
// WAVE 1: the recipe-card physical-board preview (RecipeCardBoard) migrated OFF
// the old window.BABYLON full-CDN build and ONTO the shared engine.
// WAVE 2 (Trial 5, this file): the warm sheen-rim ambient halo (SheenRim) — a
// matte physics-based-rendering plane with sheen only, mounted behind the header
// title as a low-z backing plane. Extends the same Wave 0 harness (shared engine
// + device gate + brand palette). Deep imports only (never the @babylonjs/core
// barrel) so esbuild tree-shakes.

import { Animation } from "@babylonjs/core/Animations/animation";
import { EasingFunction, SineEase } from "@babylonjs/core/Animations/easing";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { FreeCamera } from "@babylonjs/core/Cameras/freeCamera";
import { Engine } from "@babylonjs/core/Engines/engine";
import { DirectionalLight } from "@babylonjs/core/Lights/directionalLight";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { PointLight } from "@babylonjs/core/Lights/pointLight";
import { PBRMaterial } from "@babylonjs/core/Materials/PBR/pbrMaterial";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial";
import { DynamicTexture } from "@babylonjs/core/Materials/Textures/dynamicTexture";
import { RawTexture } from "@babylonjs/core/Materials/Textures/rawTexture.js";
import { Texture } from "@babylonjs/core/Materials/Textures/texture.js";
import { MultiMaterial } from "@babylonjs/core/Materials/multiMaterial";
import { Color3, Color4 } from "@babylonjs/core/Maths/math.color";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder";
import { SubMesh } from "@babylonjs/core/Meshes/subMesh";
import { Scene } from "@babylonjs/core/scene";
import { Logger } from "@babylonjs/core/Misc/logger";
import { ShaderStore } from "@babylonjs/core/Engines/shaderStore";

// ArcRotateCamera pointer/keyboard controls are registered as a side-effect;
// the camera input manager is not pulled in by the class import alone.
import "@babylonjs/core/Cameras/Inputs/arcRotateCameraPointersInput.js";
import "@babylonjs/core/Cameras/Inputs/arcRotateCameraKeyboardMoveInput.js";
import "@babylonjs/core/Cameras/Inputs/arcRotateCameraMouseWheelInput.js";

// Trial 4 — matte paperboard. clearCoat and detailMap are physics-based-rendering
// material plugin configurations on PBRMaterial; importing these deep modules
// registers the plugins as a side-effect. Deep imports only so esbuild keeps the
// tree shaken. Literal Babylon module path tokens kept as-is.
import "@babylonjs/core/Materials/PBR/pbrClearCoatConfiguration.js"; // registers clearCoat
import "@babylonjs/core/Materials/material.detailMapConfiguration.js"; // registers detailMap

Logger.LogLevels = Logger.WarningLogLevel | Logger.ErrorLogLevel;

// fixed brand palette — tokens only. Color3 is 0..1 linear.
function hex(h) {
	return Color3.FromHexString(h);
}
// Palette constants live here so later-wave scene code references one source of
// truth. Frozen and exported as _palette so the harness-only build keeps them
// live (no unused-symbol lint noise) until the scenes consume them by name.
const BLAZE = hex("#E8530E"); // Blaze Orange — 8px bar signature
const AMBER = hex("#FF8A3D"); // Warm Amber Glow
const PEACH = hex("#FFB07A"); // Blaze Peach
const TERRACOTTA = hex("#AA3F0F"); // Ember Terracotta
const BEAR = hex("#3B2316"); // Bear Brown
const PARCHMENT = hex("#FFF8F0"); // Parchment
// Signal Red #B51E14 is a fixed token but unused by these trials — omitted so
// lint stays clean. Reintroduce as hex("#B51E14") if a future effect needs it.
const _palette = Object.freeze({
	BLAZE,
	AMBER,
	PEACH,
	TERRACOTTA,
	BEAR,
	PARCHMENT,
});

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
// gateReason — SELF-DIAGNOSING gate. Returns a structured { code, message }
// explaining exactly why 3D cannot mount, or null when it CAN. The checks run in
// the SAME order canMount3D historically used, so the returned reason always
// matches the actual refusing condition. This is the single source of truth for
// the gate; canMount3D is a thin boolean wrapper over it. No condition here is
// looser than the original gate — SwiftShader software rendering and Reduce
// Motion still refuse exactly as strictly as before.
function gateReason(host) {
	if (typeof document === "undefined")
		return { code: "no-document", message: "3D preview needs a browser document." };
	const probe = probeWebGL();
	if (!probe.available)
		return {
			code: "no-webgl",
			message:
				"3D preview is off because this browser has WebGL disabled or unavailable. Showing the static image.",
		};
	if (SOFTWARE_RE.test(probe.renderer))
		return {
			code: "software-renderer",
			// include the detected renderer so the owner sees exactly what was found
			renderer: probe.renderer,
			message:
				"3D preview needs hardware graphics acceleration — this browser is using software rendering (SwiftShader). Enable hardware acceleration (see chrome://gpu) to view the 3D board. Showing the static image.",
		};
	if (prefersReducedMotion())
		return {
			code: "reduced-motion",
			message:
				"3D preview is turned off because your system has Reduce Motion enabled (an accessibility setting). Showing the static image.",
		};
	if (!host || host.clientWidth === 0 || host.clientHeight === 0)
		return {
			code: "no-layout",
			message: "3D preview could not size its container yet. Showing the static image.",
		};
	return null; // all conditions pass — 3D can mount
}
// canMount3D — thin wrapper over gateReason. Identical behavior to the prior
// direct-check version: it returns true only when every gate condition passes.
function canMount3D(host) {
	return gateReason(host) === null;
}

// ── Wave 1 — recipe-card physical-board preview ──
// Ported from the retired classic web/.../js/recipe-card-board.js. Same behavior:
// a thin box at 8.5x11in aspect + 20pt thickness, matte low-specular material,
// brown-kraft default with substrate sync, a representational front-face
// DynamicTexture, a calm ArcRotateCamera clamped to a narrow arc, gentle idle
// rotation, pause-on-interaction, reduced-motion disables idle spin, reset-view
// control + keyboard nudge. Runs ONLY on the shared engine singleton.
//
// SOURCE OF TRUTH NOTE: this preview is a REPRESENTATION only. Print geometry is
// owned by recipe-card.json + CSS. The 8.5x11 / 20pt numbers here exist to make
// the mesh read as a real board, not to specify manufacturing.

// print-geometry representation (NOT authoritative)
const RCB_CARD_W_IN = 8.5;
const RCB_CARD_H_IN = 11;
const RCB_BOARD_PT = 20;
const RCB_THICKNESS_IN = RCB_BOARD_PT / 72; // 20pt -> inches (1 pt = 1/72 in)
const RCB_WIDTH = RCB_CARD_W_IN;
const RCB_HEIGHT = RCB_CARD_H_IN;
const RCB_THICKNESS = RCB_THICKNESS_IN;

// substrate palette — matte board colors read under matte lighting.
const RCB_SUBSTRATES = {
	kraft: { r: 0.231, g: 0.137, b: 0.086, label: "kraft board" },
	white_cardstock: { r: 0.949, g: 0.933, b: 0.902, label: "white cardstock" },
	cream_parchment: { r: 0.929, g: 0.89, b: 0.804, label: "cream parchment" },
};
const RCB_DEFAULT_SUBSTRATE = "kraft";

// camera framing — calm, clamped.
const RCB_CAM = {
	alpha: -Math.PI / 2, // face-on, looking at the front
	beta: Math.PI / 2.35, // slightly above center
	radius: 20,
	alphaMin: -Math.PI / 2 - 0.6, // clamp horizontal orbit to a narrow arc
	alphaMax: -Math.PI / 2 + 0.6,
	betaMin: Math.PI / 3.2, // clamp vertical so it never flips
	betaMax: Math.PI / 1.9,
	radiusMin: 15,
	radiusMax: 28,
};
const RCB_IDLE_SPEED = 0.0016; // gentle idle rotation (radians/frame-ish)
const RCB_NUDGE = 0.08; // keyboard nudge per arrow press

function rcbReadSubstrate(container) {
	const key = container.getAttribute("data-substrate") || RCB_DEFAULT_SUBSTRATE;
	return RCB_SUBSTRATES[key] ? key : RCB_DEFAULT_SUBSTRATE;
}

class RecipeCardBoard {
	constructor(canvas, container) {
		this.canvas = canvas;
		this.container = container;
		this.engine = ensureEngine();
		this.interacting = false;
		this._idleDir = RCB_IDLE_SPEED;
		this._reduceMotion = prefersReducedMotion();

		const scene = new Scene(this.engine);
		scene.clearColor = new Color4(0, 0, 0, 0); // transparent — sit on section bg
		this.scene = scene;

		// camera — arc rotate, clamped calm range
		const cam = new ArcRotateCamera(
			"rcbCam",
			RCB_CAM.alpha,
			RCB_CAM.beta,
			RCB_CAM.radius,
			Vector3.Zero(),
			scene,
		);
		cam.attachControl(canvas, true);
		cam.lowerAlphaLimit = RCB_CAM.alphaMin;
		cam.upperAlphaLimit = RCB_CAM.alphaMax;
		cam.lowerBetaLimit = RCB_CAM.betaMin;
		cam.upperBetaLimit = RCB_CAM.betaMax;
		cam.lowerRadiusLimit = RCB_CAM.radiusMin;
		cam.upperRadiusLimit = RCB_CAM.radiusMax;
		cam.wheelDeltaPercentage = 0.01; // slow, calm zoom
		cam.panningSensibility = 0; // disable panning — keep board centered
		cam.inertia = 0.85;
		this.camera = cam;

		// soft, even lighting for a matte read
		const hemi = new HemisphericLight(
			"rcbHemi",
			new Vector3(0.2, 1, 0.3),
			scene,
		);
		hemi.intensity = 0.9;
		hemi.groundColor = new Color3(0.35, 0.3, 0.26);
		const dir = new DirectionalLight(
			"rcbDir",
			new Vector3(-0.4, -0.7, -0.6),
			scene,
		);
		dir.intensity = 0.35;

		// board mesh — a thin box, correct aspect + relative thickness.
		const board = MeshBuilder.CreateBox(
			"rcbBoard",
			{ width: RCB_WIDTH, height: RCB_HEIGHT, depth: RCB_THICKNESS },
			scene,
		);
		this.board = board;

		// edge/back material — solid matte board color, low specular
		this.boardMat = new StandardMaterial("rcbBoardMat", scene);
		// front-face material — representational texture of the card
		this.frontMat = new StandardMaterial("rcbFrontMat", scene);

		// multi-material so the front face differs from edges/back.
		// Babylon CreateBox index order is back(-z), front(+z), right, left, top,
		// bottom; each face is 6 indices (2 tris). At default alpha the +z face
		// points at the camera, so submesh 1 (indices 6..11) gets the printed front.
		const multi = new MultiMaterial("rcbMulti", scene);
		multi.subMaterials = [this.boardMat, this.frontMat];
		board.material = multi;

		this.applySubstrate(RCB_SUBSTRATES[rcbReadSubstrate(container)]);

		const totalVerts = board.getTotalVertices();
		board.subMeshes = [];
		new SubMesh(0, 0, totalVerts, 0, 6, board); // back (-z) -> boardMat
		new SubMesh(1, 0, totalVerts, 6, 6, board); // front (+z) -> frontMat
		new SubMesh(0, 0, totalVerts, 12, 24, board); // sides/top/bottom -> boardMat

		this.attachInteraction();
		this.attachKeyboard();
		this.injectResetButton();
		this.attachSubstrateObserver();

		// idle rotation lives in the scene's beforeRender; the shared master tick
		// drives the actual scene.render() via the registered customRender below.
		scene.registerBeforeRender(() => {
			if (this._reduceMotion || this.interacting) return;
			cam.alpha += this._idleDir;
			if (cam.alpha >= RCB_CAM.alphaMax || cam.alpha <= RCB_CAM.alphaMin) {
				this._idleDir = -this._idleDir;
			}
		});

		registerSceneView(canvas, cam, () => scene.render());
	}

	// build a representational front-face texture: kraft-toned panel + title.
	// deliberately simple — NOT pixel-authoritative to the real card.
	buildFrontTexture(substrateColor) {
		const size = { width: 512, height: 662 }; // ~8.5:11
		const tex = new DynamicTexture("rcbFront", size, this.scene, false);
		const ctx = tex.getContext();

		ctx.fillStyle = `rgb(${Math.round(substrateColor.r * 255)},${Math.round(
			substrateColor.g * 255,
		)},${Math.round(substrateColor.b * 255)})`;
		ctx.fillRect(0, 0, size.width, size.height);

		// keyline frame
		ctx.strokeStyle = "#3B2316";
		ctx.lineWidth = 3;
		ctx.strokeRect(28, 28, size.width - 56, size.height - 56);

		// title (heavy display feel)
		ctx.textAlign = "center";
		ctx.fillStyle = "#3B2316";
		ctx.font = 'bold 46px Georgia, "Times New Roman", serif';
		ctx.fillText("SUNSHINE", size.width / 2, 120);
		ctx.fillStyle = "#E8530E";
		ctx.fillText("LEMON CAKE", size.width / 2, 172);

		// meta bar (frontier green)
		ctx.strokeStyle = "#1A3C34";
		ctx.lineWidth = 2;
		ctx.strokeRect(70, 210, size.width - 140, 34);
		ctx.fillStyle = "#1A3C34";
		ctx.font = "18px Georgia, serif";
		ctx.fillText("PREP 20 . BAKE 35 . SERVES 8", size.width / 2, 233);

		// two-column body hint (line-art)
		ctx.strokeStyle = "rgba(59,35,22,0.55)";
		ctx.lineWidth = 2;
		let y = 300;
		for (let i = 0; i < 8; i++) {
			ctx.beginPath();
			ctx.moveTo(80, y);
			ctx.lineTo(230, y);
			ctx.stroke();
			ctx.beginPath();
			ctx.moveTo(282, y);
			ctx.lineTo(432, y);
			ctx.stroke();
			y += 30;
		}

		// footer accent (blaze orange)
		ctx.strokeStyle = "#E8530E";
		ctx.lineWidth = 4;
		ctx.beginPath();
		ctx.moveTo(70, size.height - 90);
		ctx.lineTo(size.width - 70, size.height - 90);
		ctx.stroke();

		tex.update();
		return tex;
	}

	applySubstrate(substrateColor) {
		// edge/back material (solid matte board color, low specular)
		this.boardMat.diffuseColor = new Color3(
			substrateColor.r,
			substrateColor.g,
			substrateColor.b,
		);
		this.boardMat.specularColor = new Color3(0.04, 0.04, 0.04); // matte
		this.boardMat.specularPower = 8;

		// front face texture reflects substrate too
		if (this.frontMat.diffuseTexture) this.frontMat.diffuseTexture.dispose();
		this.frontMat.diffuseTexture = this.buildFrontTexture(substrateColor);
		this.frontMat.specularColor = new Color3(0.03, 0.03, 0.03);
		this.frontMat.specularPower = 8;
	}

	resetView() {
		if (!this.camera) return;
		this.camera.alpha = RCB_CAM.alpha;
		this.camera.beta = RCB_CAM.beta;
		this.camera.radius = RCB_CAM.radius;
	}

	attachInteraction() {
		// pause idle rotation while the user drags / scrolls the view
		this._onPointerDown = () => {
			this.interacting = true;
		};
		this._onPointerUp = () => {
			this.interacting = false;
		};
		this._onWheel = () => {
			this.interacting = true;
			clearTimeout(this._wheelT);
			this._wheelT = setTimeout(() => {
				this.interacting = false;
			}, 600);
		};
		this.canvas.addEventListener("pointerdown", this._onPointerDown);
		window.addEventListener("pointerup", this._onPointerUp);
		this.canvas.addEventListener("wheel", this._onWheel, { passive: true });
	}

	attachKeyboard() {
		const cam = this.camera;
		this._onKeyDown = (ev) => {
			let handled = true;
			switch (ev.key) {
				case "ArrowLeft":
					cam.alpha = Math.max(RCB_CAM.alphaMin, cam.alpha - RCB_NUDGE);
					break;
				case "ArrowRight":
					cam.alpha = Math.min(RCB_CAM.alphaMax, cam.alpha + RCB_NUDGE);
					break;
				case "ArrowUp":
					cam.beta = Math.max(RCB_CAM.betaMin, cam.beta - RCB_NUDGE);
					break;
				case "ArrowDown":
					cam.beta = Math.min(RCB_CAM.betaMax, cam.beta + RCB_NUDGE);
					break;
				case "r":
				case "R":
					this.resetView();
					break;
				default:
					handled = false;
			}
			if (handled) ev.preventDefault();
		};
		this.canvas.addEventListener("keydown", this._onKeyDown);
	}

	injectResetButton() {
		const btn = document.createElement("button");
		btn.type = "button";
		btn.className = "recipe-card-board__reset";
		btn.textContent = "Reset view";
		btn.style.position = "absolute";
		btn.style.right = "8px";
		btn.style.bottom = "8px";
		btn.style.zIndex = "2";
		btn.style.font = "12px system-ui, sans-serif";
		btn.style.padding = "4px 8px";
		btn.style.cursor = "pointer";
		btn.addEventListener("click", () => this.resetView());
		if (getComputedStyle(this.container).position === "static") {
			this.container.style.position = "relative";
		}
		this.container.appendChild(btn);
		this._resetBtn = btn;
	}

	attachSubstrateObserver() {
		if (typeof MutationObserver === "undefined") return;
		this.substrateObserver = new MutationObserver((muts) => {
			for (const m of muts) {
				if (m.attributeName === "data-substrate") {
					this.applySubstrate(RCB_SUBSTRATES[rcbReadSubstrate(this.container)]);
					break;
				}
			}
		});
		this.substrateObserver.observe(this.container, { attributes: true });
	}

	dispose() {
		if (this.substrateObserver) this.substrateObserver.disconnect();
		if (this._onPointerDown)
			this.canvas.removeEventListener("pointerdown", this._onPointerDown);
		if (this._onPointerUp)
			window.removeEventListener("pointerup", this._onPointerUp);
		if (this._onWheel) this.canvas.removeEventListener("wheel", this._onWheel);
		if (this._onKeyDown)
			this.canvas.removeEventListener("keydown", this._onKeyDown);
		if (this._resetBtn) this._resetBtn.remove();
		clearTimeout(this._wheelT);
		this.scene.dispose();
		unregisterSceneView(this.canvas);
	}
}

function rcbShowFallback(container, visible) {
	const img = container.querySelector(".recipe-card-board__fallback");
	if (img) img.style.display = visible ? "" : "none";
}
function rcbSetStatus(container, msg) {
	const el = container.querySelector(".recipe-card-board__status");
	if (el) el.textContent = msg || "";
}

// mountRecipeCardBoard — lazy, gated mount of the physical-board preview.
// The static SVG fallback is the DEFAULT visual; the 3D board only replaces it
// after canMount3D(host) passes. Mount is deferred via IntersectionObserver so
// the scene is never built on page load — only when the section approaches view.
function mountRecipeCardBoard(selector = "#recipe-card-board") {
	const container =
		typeof selector === "string"
			? document.querySelector(selector)
			: selector;
	if (!container) return null;

	// fallback is the default visible state
	rcbShowFallback(container, true);

	const state = { board: null, mounted: false };

	const tryMount = () => {
		if (state.mounted) return; // never leak a second scene
		const reason = gateReason(container);
		if (reason) {
			// gate fail -> leave the static fallback standing, no board.
			// Surface the STRUCTURED reason so the owner sees why it gated off,
			// not a generic "unavailable" line.
			rcbShowFallback(container, true);
			rcbSetStatus(container, reason.message);
			return;
		}
		state.mounted = true;
		const canvas = document.createElement("canvas");
		canvas.className = "recipe-card-board__canvas";
		canvas.style.width = "100%";
		canvas.style.height = "100%";
		canvas.style.display = "block";
		canvas.style.outline = "none";
		canvas.setAttribute("tabindex", "0"); // focusable for keyboard nudge
		canvas.setAttribute(
			"aria-label",
			"Interactive 3D board preview. Arrow keys orbit within a limited range. Press R or the reset button to recenter.",
		);
		container.appendChild(canvas);
		try {
			state.board = new RecipeCardBoard(canvas, container);
			rcbShowFallback(container, false);
			rcbSetStatus(container, "");
		} catch (err) {
			state.mounted = false;
			canvas.remove();
			// construction failure is DISTINCT from a gate refusal — the gate
			// passed but the scene could not be built. Include the real error
			// so the next report names the cause instead of a generic line.
			const detail =
				err && err.message ? String(err.message).slice(0, 160) : String(err);
			rcbShowFallback(container, true);
			rcbSetStatus(
				container,
				"3D preview failed to start (" + detail + "). Showing the static image.",
			);
		}
	};

	if ("IntersectionObserver" in window) {
		const io = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					if (e.isIntersecting) {
						io.disconnect();
						tryMount();
						break;
					}
				}
			},
			{ rootMargin: "200px 0px" }, // approach the viewport before mounting
		);
		io.observe(container);
	} else {
		tryMount();
	}
	return state;
}

// ── Wave 2 — Trial 5: Warm Sheen Rim (matte fiber halo behind display type) ──
// runbook docs/babylonjs-integration-runbook.md section 16. A matte plane with
// physics-based-rendering sheen ONLY (no clearCoat, no particles) that produces
// a soft warm retroreflective halo at grazing angles — matte paper that glows
// faintly at the edge, not a shiny surface. It sits at ~1-2% presence directly
// behind the header title, never over it. The only motion is a very slow ambient
// light "breathe" (140-frame SineEase, ~4.6s), the same tempo Trial 1 uses.
// Runs ONLY on the shared engine singleton; reduced-motion keeps it static.

// procedural 32x32 tangent-space normal texture (runbook section 9). A crossed
// kraft-fiber pattern generated in memory as a RawTexture — zero raster asset,
// file:// safe. Gives the sheen halo real fiber to catch at grazing angles
// instead of reading as flat plastic.
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

// procedural 32x32 finer second-octave fiber texture (runbook section 15). A
// higher-frequency companion to kraftNormalTexture, packed as one RawTexture:
// RG = tangent-space normal, B = roughness variance, A = albedo detail fleck.
// Zero raster asset, file:// safe. Feeds the physics-based-rendering detailMap so
// large matte cards never read "too clean" — it adds a second fiber octave on top
// of the base weave.
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

class SheenRim {
	constructor(canvas, host) {
		this.canvas = canvas;
		this.host = host;
		this.engine = ensureEngine();
		this._reduceMotion = prefersReducedMotion();
		this.scene = new Scene(this.engine);
		this.scene.clearColor = new Color4(0, 0, 0, 0); // transparent — sit on the header band
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
		// reduced-motion: leave the light static at its base intensity — no breathe.
		if (this._reduceMotion) return;
		// reuse Trial 1's 140-frame SineEase tempo on light intensity (~4.6s at 30fps)
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

// mountSheenRim — lazy, gated mount of the ambient warm-sheen halo behind the
// header title. The CSS radial-glow fallback (owned by the stylesheet) is the
// DEFAULT visual and stands on its own; there is no fallback image to toggle
// here. The 3D halo only mounts after canMount3D(host) passes, and only when the
// host approaches the viewport (IntersectionObserver, ~200px rootMargin). On
// gate-fail or any construction error we do nothing — the CSS fallback remains.
// The overlay canvas is purely ambient: non-interactive (pointer-events none),
// aria-hidden, and z-index behind the text the CSS agent places at z-index 1.
function mountSheenRim(selector = "#kodiak-sheen-rim") {
	const host =
		typeof selector === "string"
			? document.querySelector(selector)
			: selector;
	if (!host) return null;

	const state = { rim: null, mounted: false };

	const tryMount = () => {
		if (state.mounted) return; // never leak a second scene
		const reason = gateReason(host);
		if (reason) {
			// gate fail -> CSS radial-glow fallback stands. No status element here,
			// so surface the reason as a quiet, one-shot developer diagnostic.
			console.info("KodiakEmber sheen-rim:", reason.message);
			return;
		}
		state.mounted = true;
		const canvas = document.createElement("canvas");
		canvas.className = "kodiak-sheen-rim__canvas";
		// ambient-only overlay: never interactive, always behind the header text.
		canvas.style.cssText =
			"position:absolute;inset:0;width:100%;height:100%;display:block;pointer-events:none;z-index:0";
		canvas.setAttribute("aria-hidden", "true");
		if (getComputedStyle(host).position === "static") {
			host.style.position = "relative";
		}
		host.appendChild(canvas);
		try {
			state.rim = new SheenRim(canvas, host);
		} catch {
			// silent failure — remove the dead canvas, leave the CSS fallback.
			state.mounted = false;
			canvas.remove();
		}
	};

	if ("IntersectionObserver" in window) {
		const io = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					if (e.isIntersecting) {
						io.disconnect();
						tryMount();
						break;
					}
				}
			},
			{ rootMargin: "200px 0px" }, // approach the viewport before mounting
		);
		io.observe(host);
	} else {
		tryMount();
	}
	return state;
}

// ── Wave 2 — Trial 4: Matte Paperboard Card (uncoated recycled board base +
// UV spot-gloss coat) ── runbook docs/babylonjs-integration-runbook.md section 15.
// A matte physics-based-rendering plane that reads as uncoated kraft paperboard
// (high roughness + warm sheen) wearing a thin partial clearCoat gloss layer. A
// warm PointLight rakes across the surface following the pointer (idle lissajous
// when the pointer is quiet), so a sharp spot-gloss highlight travels the surface
// exactly like light turning across UV spot-coating on a real printed box. A
// detailMap adds a finer second fiber octave so large cards never read too clean.
// Sits BEHIND content at z-index 0 — the overlay canvas is pointer-events none
// for layout, but the class still listens to pointermove on the host to drive the
// rake. Text legibility untouched. Runs ONLY on the shared engine singleton;
// reduced-motion holds the raking light at a fixed resting position.
class PaperboardCard {
	constructor(canvas, host) {
		this.canvas = canvas;
		this.host = host;
		this.engine = ensureEngine();
		this._reduceMotion = prefersReducedMotion();
		this.scene = new Scene(this.engine);
		this.scene.clearColor = new Color4(0, 0, 0, 0); // transparent — sit on the card bg
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
		// raking warm light — the spot-gloss catcher. Its resting position is the
		// center of the card; attachPointerDrift moves it from here.
		this._rakeRest = new Vector3(0, 0, -1.4);
		this.rake = new PointLight("boardRake", this._rakeRest.clone(), this.scene);
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
		// ── matte uncoated recycled-board base ──
		mat.albedoColor = hex("#F0E4D4"); // kraft surface base token (gradient.kraft.surface base)
		mat.metallic = 0; // paper is never metal
		mat.roughness = 0.9; // matte fiber — the uncoated board
		// ── warm fiber sheen (the raised-fiber glow) ──
		mat.sheen.isEnabled = true;
		mat.sheen.intensity = 0.35;
		mat.sheen.color = BLAZE.scale(0.5); // warm, derived from blazeOrange token; subtle
		// ── UV spot-gloss coat (matte base, glossy coat) ──
		mat.clearCoat.isEnabled = true;
		mat.clearCoat.intensity = 0.6; // partial coat, like selective spot-coating
		mat.clearCoat.roughness = 0.12; // sharp gloss the matte base cannot produce
		// ── base fiber normal (reuse the procedural kraft normal from section 9) ──
		const baseNormal = kraftNormalTexture(this.scene);
		baseNormal.uScale = 8;
		baseNormal.vScale = 6;
		mat.bumpTexture = baseNormal;
		// ── detailMap: finer second fiber octave ──
		mat.detailMap.isEnabled = true;
		mat.detailMap.texture = kraftDetailTexture(this.scene); // procedural, RawTexture, file:// safe
		mat.detailMap.bumpLevel = 0.6; // fine grain on top of the base weave
		mat.detailMap.roughnessBlendLevel = 0.3; // vary matte-ness across the fiber
		mat.detailMap.diffuseBlendLevel = 0.08; // barely-there tonal fleck (1-2% rule)

		plane.material = mat;
		this.plane = plane;
		this._mat = mat;
		this.attachPointerDrift(); // rakes this.rake from pointer, idle lissajous
		registerSceneView(canvas, this.camera, () => this.scene.render());
	}

	// attachPointerDrift — self-contained (Trial 2 / KraftCard is not present in
	// this file, so this does NOT depend on it). The raking PointLight follows the
	// pointer over the card while the pointer moves; when the pointer is quiet the
	// light drifts on a slow idle lissajous. reduced-motion: hold the light at its
	// fixed resting position — no pointer loop, no lissajous, a static raking
	// highlight. The drift is subtle (behind content, 1-2% presence): pointer
	// offsets map to roughly +/-1.2 world units across the plane.
	attachPointerDrift() {
		// reduced-motion: static raking highlight, nothing attached.
		if (this._reduceMotion) return;

		const DRIFT = 1.2; // world-unit half-range the light travels across the card
		this._pointerActive = false;
		this._lastMove = 0;
		this._t0 =
			typeof performance !== "undefined" ? performance.now() : Date.now();

		this._onMove = (ev) => {
			const rect = this.host.getBoundingClientRect();
			if (!rect.width || !rect.height) return;
			// normalize pointer to -1..1 over the host, map onto the card plane.
			const nx = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
			const ny = ((ev.clientY - rect.top) / rect.height) * 2 - 1;
			this.rake.position.x = nx * DRIFT;
			this.rake.position.y = -ny * DRIFT; // screen-y is down; world-y is up
			this._pointerActive = true;
			this._lastMove =
				typeof performance !== "undefined" ? performance.now() : Date.now();
		};
		this.host.addEventListener("pointermove", this._onMove);

		// idle lissajous: when the pointer has been quiet ~1.2s, sweep the rake on
		// a slow two-frequency curve so the spot-gloss keeps travelling gently.
		this.scene.registerBeforeRender(() => {
			const now =
				typeof performance !== "undefined" ? performance.now() : Date.now();
			if (this._pointerActive && now - this._lastMove < 1200) return;
			this._pointerActive = false;
			const t = (now - this._t0) / 1000;
			this.rake.position.x = Math.sin(t * 0.35) * DRIFT;
			this.rake.position.y = Math.sin(t * 0.24 + Math.PI / 3) * DRIFT * 0.6;
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

// mountPaperboardCards — lazy, gated, CAPPED mount of the matte paperboard layer
// across .card surfaces.
//
// VIEW-COUNT / CAP POLICY (stated per runbook section 11 >=30fps mid-tier iGPU
// budget): details.html carries ~29 .card surfaces. Mounting 29 physics-based-
// rendering scene views on the shared engine for a 1-2% ambient effect would blow
// the frame budget. This policy is: (1) a HARD CAP of PAPERBOARD_MAX_VIEWS = 6
// simultaneously-mounted views; (2) LAZY per-card build via IntersectionObserver
// so only cards near the viewport ever construct a scene; (3) when a mounted card
// scrolls far away it is disposed and its cap slot freed, so as the reader scrolls
// the 6 live views ride the viewport rather than accumulating. The device gate
// (canMount3D) still applies per card. The existing CSS kraft gradient
// (--gradients-kraft / gradient.kraft.surface token) is the DEFAULT card surface
// and stands whenever a card is not 3D-mounted — there is no fallback element to
// toggle, the stylesheet already provides the card look. On any construction
// failure the try/catch silently leaves the CSS card surface.
const PAPERBOARD_MAX_VIEWS = 6; // hard simultaneous-view cap (frame-budget guard)

function mountPaperboardCards(selector = ".card") {
	const cards = document.querySelectorAll(selector);
	if (!cards.length) return null;

	const state = { cards: [], live: 0 };
	// per-card record: { host, card (PaperboardCard|null), canvas, mounted }
	const records = [];

	const mountOne = (rec) => {
		if (rec.mounted) return; // never leak a second scene on one host
		if (state.live >= PAPERBOARD_MAX_VIEWS) return; // cap — CSS surface stands
		const reason = gateReason(rec.host);
		if (reason) {
			// gate fail -> CSS kraft gradient stands. No status element on cards,
			// so surface the reason as a quiet developer diagnostic — once per
			// card, guarded so IntersectionObserver re-entries do not spam it.
			if (!rec.gateLogged) {
				rec.gateLogged = true;
				console.info("KodiakEmber paperboard-card:", reason.message);
			}
			return;
		}
		rec.mounted = true;
		const canvas = document.createElement("canvas");
		canvas.className = "kodiak-paperboard__canvas";
		// ambient-only overlay: never interactive, always behind card content.
		canvas.style.cssText =
			"position:absolute;inset:0;width:100%;height:100%;display:block;pointer-events:none;z-index:0";
		canvas.setAttribute("aria-hidden", "true");
		if (getComputedStyle(rec.host).position === "static") {
			rec.host.style.position = "relative";
		}
		rec.host.appendChild(canvas);
		rec.canvas = canvas;
		try {
			rec.card = new PaperboardCard(canvas, rec.host);
			state.live++;
		} catch {
			// silent failure — remove the dead canvas, leave the CSS card surface.
			rec.mounted = false;
			canvas.remove();
			rec.canvas = null;
		}
	};

	const disposeOne = (rec) => {
		if (!rec.mounted) return;
		if (rec.card) {
			try {
				rec.card.dispose();
			} catch {
				/* best-effort: still free the slot + canvas below */
			}
			rec.card = null;
		}
		if (rec.canvas) {
			rec.canvas.remove();
			rec.canvas = null;
		}
		rec.mounted = false;
		if (state.live > 0) state.live--;
	};

	if ("IntersectionObserver" in window) {
		const io = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					const rec = records.find((r) => r.host === e.target);
					if (!rec) continue;
					if (e.isIntersecting) mountOne(rec);
					else disposeOne(rec); // scrolled far away -> free the cap slot
				}
			},
			// mount as a card approaches; the negative-margin dispose band means a
			// card only tears down once it is well outside the viewport.
			{ rootMargin: "200px 0px" },
		);
		cards.forEach((host) => {
			const rec = { host, card: null, canvas: null, mounted: false };
			records.push(rec);
			io.observe(host);
		});
		state.observer = io;
	} else {
		// no IntersectionObserver: mount up to the cap from the top of the list.
		cards.forEach((host) => {
			const rec = { host, card: null, canvas: null, mounted: false };
			records.push(rec);
			mountOne(rec);
		});
	}
	state.cards = records;
	return state;
}

// ── public API (WAVE 1 surface) ──
// Later waves add mountEmberBar / mountKraftCards / finishLineBloom here. This
// wave exposes the recipe-card board mount plus the device gate and version
// stamp, so the details.html <script> boot guard is wireable and testable now.
const KodiakEmber = {
	mountRecipeCardBoard,
	mountSheenRim,
	mountPaperboardCards,
	canMount3D,
	gateReason,
	_version: "0.5.0",
	// harness internals surfaced for later-wave scene modules + tests; not a
	// stable public contract.
	_harness: Object.freeze({
		ensureEngine,
		registerSceneView,
		unregisterSceneView,
		probeWebGL,
		prefersReducedMotion,
	}),
	_palette,
};
if (typeof window !== "undefined") window.KodiakEmber = KodiakEmber;
export { KodiakEmber };
