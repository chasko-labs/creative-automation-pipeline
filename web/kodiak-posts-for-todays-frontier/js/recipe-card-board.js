/*
 * recipe-card-board.js — supplementary BabylonJS "physical board" preview.
 *
 * Classic deferred script. NO modules, NO bundler. Guards on window.BABYLON,
 * which is loaded by a separately pinned CDN <script> in details.html.
 *
 * SOURCE OF TRUTH NOTE: this preview is a representation only. Print geometry
 * is owned by recipe-card.json + CSS. The 8.5 x 11 / 20pt numbers here exist
 * to make the mesh read as a real board, not to specify manufacturing.
 *
 * Ownership boundary: the section markup, substrate switch, wireframe toggle,
 * styles.css and the #recipe-card-board CONTAINER are owned by another agent.
 * This script only hooks the container and mounts a canvas inside it.
 */
(function () {
  'use strict';

  // ---- print-geometry representation (NOT authoritative) --------------------
  var UNITS_PER_INCH = 1;                 // scene units per inch
  var CARD_W_IN = 8.5;                    // 8.5 in wide
  var CARD_H_IN = 11;                     // 11 in tall
  var BOARD_PT = 20;                      // 20 point board
  var THICKNESS_IN = BOARD_PT / 72;       // 20pt -> inches (1 pt = 1/72 in)

  var WIDTH = CARD_W_IN * UNITS_PER_INCH;
  var HEIGHT = CARD_H_IN * UNITS_PER_INCH;
  var THICKNESS = THICKNESS_IN * UNITS_PER_INCH;

  // ---- substrate palette (matte board colors) ------------------------------
  // hex triples chosen to read as physical board stock under matte lighting.
  var SUBSTRATES = {
    kraft:           { r: 0.231, g: 0.137, b: 0.086, label: 'kraft board' },        // ~#3B2316 family, warm medium-brown
    white_cardstock: { r: 0.949, g: 0.933, b: 0.902, label: 'white cardstock' },    // warm white
    cream_parchment: { r: 0.929, g: 0.890, b: 0.804, label: 'cream parchment' }     // light cream
  };
  var DEFAULT_SUBSTRATE = 'kraft';

  // ---- camera framing (calm, clamped) --------------------------------------
  var CAM = {
    alpha: -Math.PI / 2,          // face-on, looking at the front
    beta: Math.PI / 2.35,         // slightly above center
    radius: 20,
    alphaMin: -Math.PI / 2 - 0.6, // clamp horizontal orbit to a narrow arc
    alphaMax: -Math.PI / 2 + 0.6,
    betaMin: Math.PI / 3.2,       // clamp vertical so it never flips
    betaMax: Math.PI / 1.9,
    radiusMin: 15,                // limit zoom
    radiusMax: 28
  };

  var IDLE_SPEED = 0.0016;        // gentle idle rotation (radians/frame-ish)
  var NUDGE = 0.08;               // keyboard nudge per arrow press

  var reduceMotion = false;
  try {
    reduceMotion = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (e) { reduceMotion = false; }

  var state = {
    initialized: false,   // guard so intersection re-fires never build a 2nd engine
    engine: null,
    scene: null,
    camera: null,
    board: null,
    boardMat: null,
    canvas: null,
    interacting: false,   // pause idle rotation while user drags/inputs
    substrateObserver: null
  };

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn, { once: true });
    } else {
      fn();
    }
  }

  function setStatus(container, msg) {
    var el = container.querySelector('.recipe-card-board__status');
    if (el) { el.textContent = msg || ''; }
  }

  function showFallback(container, visible) {
    var img = container.querySelector('.recipe-card-board__fallback');
    if (img) { img.style.display = visible ? '' : 'none'; }
  }

  function readSubstrate(container) {
    var key = container.getAttribute('data-substrate') || DEFAULT_SUBSTRATE;
    return SUBSTRATES[key] ? key : DEFAULT_SUBSTRATE;
  }

  // build a representational front-face texture: kraft-toned panel + title.
  // kept deliberately simple — NOT pixel-authoritative to the real card.
  function buildFrontTexture(scene, substrateColor) {
    var DT = window.BABYLON.DynamicTexture;
    var size = { width: 512, height: 662 };  // ~8.5:11
    var tex = new DT('recipe-card-front', size, scene, false);
    var ctx = tex.getContext();

    // board fill
    ctx.fillStyle = 'rgb(' +
      Math.round(substrateColor.r * 255) + ',' +
      Math.round(substrateColor.g * 255) + ',' +
      Math.round(substrateColor.b * 255) + ')';
    ctx.fillRect(0, 0, size.width, size.height);

    // keyline frame
    ctx.strokeStyle = '#3B2316';
    ctx.lineWidth = 3;
    ctx.strokeRect(28, 28, size.width - 56, size.height - 56);

    // title (heavy display feel)
    ctx.textAlign = 'center';
    ctx.fillStyle = '#3B2316';
    ctx.font = 'bold 46px Georgia, "Times New Roman", serif';
    ctx.fillText('SUNSHINE', size.width / 2, 120);
    ctx.fillStyle = '#E8530E';
    ctx.fillText('LEMON CAKE', size.width / 2, 172);

    // meta bar (frontier green)
    ctx.strokeStyle = '#1A3C34';
    ctx.lineWidth = 2;
    ctx.strokeRect(70, 210, size.width - 140, 34);
    ctx.fillStyle = '#1A3C34';
    ctx.font = '18px Georgia, serif';
    ctx.fillText('PREP 20 . BAKE 35 . SERVES 8', size.width / 2, 233);

    // two-column body hint (line-art)
    ctx.strokeStyle = 'rgba(59,35,22,0.55)';
    ctx.lineWidth = 2;
    var y = 300;
    for (var i = 0; i < 8; i++) {
      ctx.beginPath(); ctx.moveTo(80, y); ctx.lineTo(230, y); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(282, y); ctx.lineTo(432, y); ctx.stroke();
      y += 30;
    }

    // footer accent (blaze orange)
    ctx.strokeStyle = '#E8530E';
    ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(70, size.height - 90);
    ctx.lineTo(size.width - 70, size.height - 90); ctx.stroke();

    tex.update();
    return tex;
  }

  function applySubstrate(scene, substrateColor) {
    var B = window.BABYLON;
    // edge/back material (solid matte board color, low specular)
    state.boardMat.diffuseColor = new B.Color3(
      substrateColor.r, substrateColor.g, substrateColor.b);
    state.boardMat.specularColor = new B.Color3(0.04, 0.04, 0.04); // low specular = matte
    state.boardMat.specularPower = 8;

    // front face texture reflects substrate too
    if (state.frontMat) {
      if (state.frontMat.diffuseTexture) { state.frontMat.diffuseTexture.dispose(); }
      state.frontMat.diffuseTexture = buildFrontTexture(scene, substrateColor);
      state.frontMat.specularColor = new B.Color3(0.03, 0.03, 0.03);
      state.frontMat.specularPower = 8;
    }
  }

  function resetView() {
    if (!state.camera) { return; }
    state.camera.alpha = CAM.alpha;
    state.camera.beta = CAM.beta;
    state.camera.radius = CAM.radius;
  }

  function injectResetButton(container) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'recipe-card-board__reset';
    btn.textContent = 'Reset view';
    // minimal inline positioning so we do not depend on the CSS agent's styles;
    // layout/skin remains theirs to override.
    btn.style.position = 'absolute';
    btn.style.right = '8px';
    btn.style.bottom = '8px';
    btn.style.zIndex = '2';
    btn.style.font = '12px system-ui, sans-serif';
    btn.style.padding = '4px 8px';
    btn.style.cursor = 'pointer';
    btn.addEventListener('click', function () { resetView(); });
    // container may be statically positioned; ensure the button anchors to it.
    var pos = window.getComputedStyle(container).position;
    if (pos === 'static') { container.style.position = 'relative'; }
    container.appendChild(btn);
  }

  function initScene(container) {
    if (state.initialized) { return; }   // never leak a second engine

    var B = window.BABYLON;
    if (!B) {
      // remote script failed — keep fallback, calm message, do not throw.
      showFallback(container, true);
      setStatus(container, '3D board preview unavailable — showing static image');
      return;
    }

    state.initialized = true;

    // canvas
    var canvas = document.createElement('canvas');
    canvas.className = 'recipe-card-board__canvas';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.display = 'block';
    canvas.style.outline = 'none';
    canvas.setAttribute('tabindex', '0');  // focusable for keyboard nudge
    canvas.setAttribute('aria-label',
      'Interactive 3D board preview. Arrow keys orbit within a limited range. Press R or the reset button to recenter.');
    container.appendChild(canvas);
    state.canvas = canvas;

    var engine;
    try {
      engine = new B.Engine(canvas, true, { preserveDrawingBuffer: true, stencil: true });
    } catch (e) {
      // engine construction failed (e.g. no webgl) — degrade gracefully.
      state.initialized = false;
      canvas.remove();
      showFallback(container, true);
      setStatus(container, '3D board preview unavailable — showing static image');
      return;
    }
    state.engine = engine;

    var scene = new B.Scene(engine);
    scene.clearColor = new B.Color4(0, 0, 0, 0); // transparent — sit on section bg
    state.scene = scene;

    // camera — arc rotate, clamped calm range
    var cam = new B.ArcRotateCamera('cam', CAM.alpha, CAM.beta, CAM.radius,
      B.Vector3.Zero(), scene);
    cam.attachControl(canvas, true);
    cam.lowerAlphaLimit = CAM.alphaMin;
    cam.upperAlphaLimit = CAM.alphaMax;
    cam.lowerBetaLimit = CAM.betaMin;
    cam.upperBetaLimit = CAM.betaMax;
    cam.lowerRadiusLimit = CAM.radiusMin;
    cam.upperRadiusLimit = CAM.radiusMax;
    cam.wheelDeltaPercentage = 0.01;   // slow, calm zoom
    cam.panningSensibility = 0;        // disable panning — keep board centered
    cam.inertia = 0.85;
    state.camera = cam;

    // soft, even lighting for a matte read
    var hemi = new B.HemisphericLight('hemi', new B.Vector3(0.2, 1, 0.3), scene);
    hemi.intensity = 0.9;
    hemi.groundColor = new B.Color3(0.35, 0.3, 0.26);
    var dir = new B.DirectionalLight('dir', new B.Vector3(-0.4, -0.7, -0.6), scene);
    dir.intensity = 0.35;

    // board mesh — a thin box, correct aspect + relative thickness.
    // MeshBuilder.CreateBox is a static factory — no `new`.
    var board = B.MeshBuilder.CreateBox('board', {
      width: WIDTH,
      height: HEIGHT,
      depth: THICKNESS
    }, scene);
    state.board = board;

    var startColor = SUBSTRATES[readSubstrate(container)];

    // edge/back material — solid matte board color, low specular
    var boardMat = new B.StandardMaterial('boardMat', scene);
    state.boardMat = boardMat;

    // front-face material — representational texture of the card
    var frontMat = new B.StandardMaterial('frontMat', scene);
    state.frontMat = frontMat;

    // multi-material so the front face differs from edges/back.
    // Babylon CreateBox index order is: back(-z), front(+z), right, left, top, bottom;
    // each face is 6 indices (2 tris). At default alpha the +z face points at the
    // camera, so submesh 1 (indices 6..11) gets the printed front; the rest get board.
    var multi = new B.MultiMaterial('boardMulti', scene);
    multi.subMaterials = [boardMat, frontMat];
    board.material = multi;

    applySubstrate(scene, startColor);  // paint both materials from substrate

    var totalVerts = board.getTotalVertices();
    board.subMeshes = [];
    new B.SubMesh(0, 0, totalVerts, 0, 6, board);    // back (-z) -> boardMat
    new B.SubMesh(1, 0, totalVerts, 6, 6, board);    // front (+z) -> frontMat
    new B.SubMesh(0, 0, totalVerts, 12, 24, board);  // sides/top/bottom -> boardMat

    // ---- interaction pause/resume for idle rotation ----
    function pause() { state.interacting = true; }
    function resume() { state.interacting = false; }
    canvas.addEventListener('pointerdown', pause);
    window.addEventListener('pointerup', resume);
    canvas.addEventListener('wheel', function () {
      pause();
      clearTimeout(state._wheelT);
      state._wheelT = setTimeout(resume, 600);
    }, { passive: true });

    // ---- keyboard nudge within clamp + reset ----
    canvas.addEventListener('keydown', function (ev) {
      var handled = true;
      switch (ev.key) {
        case 'ArrowLeft':  cam.alpha = Math.max(CAM.alphaMin, cam.alpha - NUDGE); break;
        case 'ArrowRight': cam.alpha = Math.min(CAM.alphaMax, cam.alpha + NUDGE); break;
        case 'ArrowUp':    cam.beta = Math.max(CAM.betaMin, cam.beta - NUDGE); break;
        case 'ArrowDown':  cam.beta = Math.min(CAM.betaMax, cam.beta + NUDGE); break;
        case 'r': case 'R': resetView(); break;
        default: handled = false;
      }
      if (handled) { ev.preventDefault(); }
    });

    injectResetButton(container);

    // ---- render loop: gentle idle rotation, respects reduced motion + pause ----
    scene.registerBeforeRender(function () {
      if (!reduceMotion && !state.interacting) {
        cam.alpha += IDLE_SPEED;
        // keep idle drift inside the clamp; bounce softly at edges
        if (cam.alpha >= CAM.alphaMax || cam.alpha <= CAM.alphaMin) {
          IDLE_SPEED = -IDLE_SPEED;
        }
      }
    });

    engine.runRenderLoop(function () { scene.render(); });
    window.addEventListener('resize', function () { engine.resize(); });

    // ---- substrate sync: MutationObserver on data-substrate ----
    if (window.MutationObserver) {
      state.substrateObserver = new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          if (muts[i].attributeName === 'data-substrate') {
            applySubstrate(scene, SUBSTRATES[readSubstrate(container)]);
            break;
          }
        }
      });
      state.substrateObserver.observe(container, { attributes: true });
    }

    // scene is live — hide the fallback, clear any status.
    showFallback(container, false);
    setStatus(container, '');
  }

  // ---- lazy load orchestration --------------------------------------------
  function watchAndInit(container) {
    // If BabylonJS never loaded, we still want the fallback + message the moment
    // we would have initialized (i.e. when the section is reached).
    function tryInit() {
      if (!window.BABYLON) {
        showFallback(container, true);
        setStatus(container, '3D board preview unavailable — showing static image');
        return;
      }
      initScene(container);
    }

    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].isIntersecting) {
            io.disconnect();
            tryInit();
            break;
          }
        }
      }, { rootMargin: '200px 0px' }); // approach the viewport before mounting
      io.observe(container);
    } else {
      // fallback: one-time init on first scroll near the container
      var onScroll = function () {
        var rect = container.getBoundingClientRect();
        var near = rect.top < (window.innerHeight + 200) && rect.bottom > -200;
        if (near) {
          window.removeEventListener('scroll', onScroll);
          tryInit();
        }
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll(); // in case it is already in view
    }
  }

  onReady(function () {
    var container = document.getElementById('recipe-card-board');
    if (!container) { return; }         // section not present on this page
    showFallback(container, true);      // fallback is the default visible state
    watchAndInit(container);
  });
})();
