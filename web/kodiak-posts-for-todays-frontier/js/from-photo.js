// === From a Photo or Prompt — single-image entry point (#39) — additive, guarded ===
// VANILLA-JS BEHAVIOR track. Mirrors campaign-sections.js runCampaign() idiom for the
// already-built POST /campaigns/from-photo route (alias /campaigns/from-prompt). Mounts one
// collapsible section near the forest treeline placeholder, offline-degrades honestly, and
// reuses window.KODIAK_showRenderSet for on-screen output when generate.js has exposed it.
// The backend route is only reachable on the hosted deployment; offline shows a degrade note.
(function () {
  'use strict';

  const SECTION_ID = 'fromPhotoSection';
  const STATUS_ID = 'fromPhotoStatus';
  const BTN_ID = 'fromPhotoRun';
  const PROMPT_ID = 'fromPhotoPrompt';
  const OUT_ID = 'fromPhotoOutput';
  // single image, not the 3/4-size campaign path — a short wall timeout is plenty.
  const WALL_MS = 45000;

  // esc() — same approach as campaign-sections.js: never innerHTML a raw response field.
  function esc(s) {
    return String((s === null || s === undefined) ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Reuse the page's existing selectors when campaign-sections.js has exposed them as
  // globals; otherwise fall back to this section's own market/product inputs. These
  // readers are defensive — the from-photo route defaults market server-side when omitted.
  function selectedMarket() {
    try {
      const el = document.getElementById('locality');
      if (el && el.value) return el.value;
    } catch (e) { /* fall through to local input */ }
    try {
      const local = document.getElementById('fromPhotoMarket');
      if (local && local.value.trim()) return local.value.trim();
    } catch (e) { /* no local market input */ }
    return '';
  }

  function selectedProductSlug() {
    try {
      if (window.__requestedSku) return window.__requestedSku;
    } catch (e) { /* not set yet */ }
    try {
      const local = document.getElementById('fromPhotoProduct');
      if (local && local.value.trim()) return local.value.trim();
    } catch (e) { /* no local product input */ }
    return '';
  }

  function currentPrompt() {
    try {
      const el = document.getElementById(PROMPT_ID);
      return el ? el.value.trim() : '';
    } catch (e) {
      return '';
    }
  }

  // idempotent mount, same guard shape as campaign-sections.js ensureSections()/mountSections().
  function mountSection() {
    if (document.getElementById(SECTION_ID)) return true;
    const forest = document.querySelector('.ff-forest');
    const wrap = document.createElement('div');
    wrap.innerHTML =
      '<details id="' + SECTION_ID + '" class="ff-output ff-from-photo preview-card">' +
        '<summary aria-labelledby="fromPhotoHeading">' +
          '<span id="fromPhotoHeading" class="ff-output-heading">From a Photo or Prompt</span>' +
        '</summary>' +
        '<p class="hint">Describe a scene or riff on an uploaded hero — one localized image, straight from the backend. ' +
          'Market defaults to Atlanta when left blank.</p>' +
        '<div class="row">' +
          '<textarea id="' + PROMPT_ID + '" class="ff-from-photo-prompt" rows="3" ' +
            'aria-label="Prompt for the from-photo image" ' +
            'placeholder="e.g. Kodiak flapjacks on a trailhead picnic table at golden hour"></textarea>' +
        '</div>' +
        '<div class="row">' +
          '<button type="button" class="btn orange" id="' + BTN_ID + '" data-mcp="from-photo-generate">Generate image</button>' +
        '</div>' +
        '<div class="hint" id="' + STATUS_ID + '" role="status" aria-live="polite"></div>' +
        '<div class="ff-from-photo-output" id="' + OUT_ID + '"></div>' +
      '</details>';
    if (forest && forest.parentNode) {
      const ref = forest.nextSibling;
      while (wrap.firstChild) {
        forest.parentNode.insertBefore(wrap.firstChild, ref);
      }
    } else {
      document.body.appendChild(wrap);
    }
    wireButton();
    return true;
  }

  function setBtnDisabled(disabled) {
    const b = document.getElementById(BTN_ID);
    if (b) b.disabled = disabled;
  }

  // On success render what the response gives. Prefer the shared multi-ratio renderer
  // generate.js exposes (window.KODIAK_showRenderSet); otherwise paint a simple list of
  // ratio + iso_name + note per image. manifest.notes[] surface to the user either way.
  function renderResult(json) {
    const out = document.getElementById(OUT_ID);
    if (!out) return;
    out.innerHTML = '';

    const images = Array.isArray(json.images) ? json.images : [];
    const manifest = (json.manifest && typeof json.manifest === 'object') ? json.manifest : {};

    // reuse the hosted renderer when it exists and the shape maps (image_url expected there).
    let renderedViaShared = false;
    try {
      const renderSet = images
        .filter(function (im) { return im && (im.image_path || im.image_url); })
        .map(function (im) {
          return { image_url: im.image_url || im.image_path, ratio: im.ratio || '1x1' };
        });
      if (typeof window.KODIAK_showRenderSet === 'function' && renderSet.length) {
        window.KODIAK_showRenderSet(renderSet, { source: 'from-photo', provenance: manifest });
        renderedViaShared = true;
      }
    } catch (e) { /* shared renderer optional — fall back to the list below */ }

    if (!renderedViaShared) {
      if (images.length) {
        const list = document.createElement('ul');
        list.className = 'ff-from-photo-list';
        images.forEach(function (im) {
          if (!im) return;
          const li = document.createElement('li');
          const ratio = im.ratio ? String(im.ratio).replace('x', ':') : '';
          const iso = im.iso_name ? ' \u2014 ' + im.iso_name : '';
          li.textContent = ratio + iso;
          list.appendChild(li);
        });
        out.appendChild(list);
      } else if (json.image_path) {
        const solo = document.createElement('div');
        solo.className = 'small';
        solo.textContent = 'Image ready: ' + esc(json.image_path);
        out.appendChild(solo);
      }
    }

    // manifest.notes[] — the offline-mock note is informative; always show what came back.
    const notes = Array.isArray(manifest.notes) ? manifest.notes : [];
    if (notes.length) {
      const noteWrap = document.createElement('div');
      noteWrap.className = 'ff-from-photo-notes small';
      notes.forEach(function (n) {
        const line = document.createElement('div');
        line.className = 'loc-line';
        line.textContent = String(n);
        noteWrap.appendChild(line);
      });
      out.appendChild(noteWrap);
    }
  }

  async function runFromPhoto() {
    const status = document.getElementById(STATUS_ID);
    // offline detect — identical shape to campaign-sections.js runCampaign(); this route is
    // hosted-only, so degrade honestly and RETURN without fetching.
    const isLocal = (location.protocol === 'file:') ||
      ['127.0.0.1', 'localhost'].includes(location.hostname);
    if (isLocal) {
      if (status) status.textContent = 'From-photo needs the hosted backend — offline cannot reach this route.';
      return;
    }

    const prompt = currentPrompt();
    const market = selectedMarket();
    const product = selectedProductSlug();
    // route contract: at least a prompt OR a resolvable hero. This entry point supplies the
    // prompt; guard client-side so we never send a 400-guaranteed body.
    if (!prompt) {
      if (status) status.textContent = 'Enter a prompt first — a scene or a riff on the hero.';
      return;
    }

    setBtnDisabled(true);
    if (status) status.textContent = 'Generating one image\u2026 up to ~45s';
    const t0 = Date.now();
    try {
      if (window.ffLog) {
        window.ffLog('from-photo-start', { market: market || 'default', product: product || 'default', prompt: prompt.slice(0, 120) });
      }
    } catch (e) { /* logging is best-effort */ }

    const controller = new AbortController();
    const timeoutId = setTimeout(function () { controller.abort(); }, WALL_MS);
    try {
      // relative URL, same as the /generate call. Only send fields we have — market omitted
      // lets the backend default to Atlanta (US-SE-ATL); product omitted is allowed too.
      const body = { prompt: prompt };
      if (market) body.market = market;
      if (product) body.product = product;

      const resp = await fetch('/campaigns/from-photo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal
      });
      if (!resp.ok) throw new Error('backend returned HTTP ' + resp.status);
      let json;
      try {
        json = await resp.json();
      } catch (pe) {
        throw new Error('malformed response from backend');
      }

      renderResult(json);
      const count = Array.isArray(json.images) ? json.images.length : (json.image_path ? 1 : 0);
      if (status) {
        status.textContent = count
          ? 'Image ready \u2014 ' + count + ' render' + (count === 1 ? '' : 's') + '.'
          : 'Backend responded, but no image was returned.';
      }
      try {
        if (window.ffLog) {
          window.ffLog('from-photo-done', { ms: Date.now() - t0, images: count });
        }
      } catch (e) { /* logging is best-effort */ }
    } catch (err) {
      const timedOut = err && err.name === 'AbortError';
      if (status) {
        status.textContent = timedOut
          ? 'From-photo timed out \u2014 reconnect and try again.'
          : 'Could not generate the image \u2014 ' + (err && err.message ? err.message : 'try again') + '.';
      }
      try {
        if (window.ffLog) {
          window.ffLog('from-photo-fail', {
            kind: timedOut ? 'timeout' : 'error',
            message: String((err && err.message) || err || '').slice(0, 200),
            ms: Date.now() - t0
          });
        }
      } catch (e) { /* logging is best-effort */ }
    } finally {
      clearTimeout(timeoutId);
      setBtnDisabled(false);
    }
  }

  function wireButton() {
    const btn = document.getElementById(BTN_ID);
    if (btn && !btn.__wired) {
      btn.__wired = true;
      btn.addEventListener('click', function () { runFromPhoto(); });
    }
  }

  // exposed for tests / manual retrigger; guarded, never throws.
  try { window.KODIAK_runFromPhoto = runFromPhoto; } catch (e) { /* window optional */ }

  function init() {
    mountSection();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
