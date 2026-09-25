// Recipes surface renderer — reads window.KODIAK_RECIPE_CARDS (precomputed card-DATA,
// loaded by js/recipe-cards-data.js) and builds .rc-card DOM using the EXACT design-standard
// class structure from the details.html specimen. The rc-* CSS already exists in
// design/styles.css; this module only builds nodes, it does NOT restyle the design system.
//
// offline-safe: no fetch. if window.KODIAK_RECIPE_CARDS is undefined the gallery shows a
// graceful empty state and never throws. art zones embed the generated S3 line-art when the
// url is non-null, else fall back to an inline SVG "sketch pending" mark — never empty, never
// a broken image. no provenance markers on the card face (removed by design decision).
(function () {
  'use strict';

  var SVGNS = 'http://www.w3.org/2000/svg';

  // static corner flourish paths, lifted from the specimen (left + right mirror).
  // wheat ear corner mark: curved stem, filled kernel ellipses alternating along
  // it, three awns off the tip. filled grain reads at 1in size; no underline
  // rule — the ear stands on its own.
  var CORNER_STEM_LEFT = 'M20 94 C28 66 32 44 42 14';
  var CORNER_STEM_RIGHT = 'M80 94 C72 66 68 44 58 14';
  var CORNER_AWNS_LEFT = 'M42 14 L35 1 M42 14 L43 0 M42 14 L49 2';
  var CORNER_AWNS_RIGHT = 'M58 14 L65 1 M58 14 L57 0 M58 14 L51 2';
  // kernel triples are [x, y, rotation] — a tuple, not number[]: positions 0-1
  // are coordinates, position 2 is degrees, and mixing them up is a type error.
  /** @type {Array<[number, number, number]>} */
  var CORNER_KERNELS_LEFT = [[33,24,-25],[46,28,25],[30,36,-25],[43,40,25],[28,48,-22],[40,52,22],[26,60,-20],[37,64,20],[25,72,-15],[34,74,15]];
  /** @type {Array<[number, number, number]>} */
  var CORNER_KERNELS_RIGHT = [[67,24,25],[54,28,-25],[70,36,25],[57,40,-25],[72,48,22],[60,52,-22],[74,60,20],[63,64,-20],[75,72,15],[66,74,-15]];

  // the three artzone divs, in render order, each mapped to its data key + css modifier + data-zone.
  /** @type {{css: string, dataZone: string, artKey: 'raw_ingredient'|'technique'|'finished_plate'}[]} */
  var ART_ZONES = [
    { css: 'rc-artzone--raw', dataZone: 'raw_ingredient_sketch', artKey: 'raw_ingredient' },
    { css: 'rc-artzone--technique', dataZone: 'technique_sketch', artKey: 'technique' },
    { css: 'rc-artzone--plate', dataZone: 'finished_plate_sketch', artKey: 'finished_plate' }
  ];

  /** @type {{key: string, label: string}[]} */
  var META_CELLS = [
    { key: 'prep', label: 'Prep' },
    { key: 'cook', label: 'Cook' },
    { key: 'serves', label: 'Serves' },
    { key: 'est_cost', label: 'Est cost' }
  ];

  var EM_DASH = '\u2014';

  /**
   * @param {string} tag
   * @param {string} [cls]
   * @param {string} [text]
   * @returns {HTMLElement}
   */
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  /**
   * @param {string} tag
   * @param {Object<string, (string|number)>} [attrs]
   * @returns {Element}
   */
  function svgEl(tag, attrs) {
    var node = document.createElementNS(SVGNS, tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) { node.setAttribute(k, String(attrs[k])); });
    }
    return node;
  }

  // present a value or an honest em-dash when null/empty. never fabricates.
  /**
   * @param {unknown} v
   * @returns {string}
   */
  function orDash(v) {
    if (v == null) return EM_DASH;
    var s = String(v).trim();
    return s.length ? s : EM_DASH;
  }

  // corner accent svg — identical for every card (static flourish, matches specimen).
  /**
   * @param {string} side
   * @returns {HTMLElement}
   */
  function makeCorner(side) {
    var wrap = el('div', 'rc-corner rc-corner--' + side);
    wrap.setAttribute('data-zone', side === 'left' ? 'corner_accent_left' : 'corner_accent_right');
    wrap.setAttribute('aria-hidden', 'true');
    var svg = svgEl('svg', { viewBox: '0 0 100 100', class: 'rc-corner__art', role: 'presentation', focusable: 'false' });
    var isLeft = side === 'left';
    svg.appendChild(svgEl('path', {
      d: isLeft ? CORNER_STEM_LEFT : CORNER_STEM_RIGHT,
      fill: 'none', stroke: 'currentColor', 'stroke-width': '2.4', 'stroke-linecap': 'round'
    }));
    svg.appendChild(svgEl('path', {
      d: isLeft ? CORNER_AWNS_LEFT : CORNER_AWNS_RIGHT,
      fill: 'none', stroke: 'currentColor', 'stroke-width': '1.4', 'stroke-linecap': 'round'
    }));
    (isLeft ? CORNER_KERNELS_LEFT : CORNER_KERNELS_RIGHT).forEach(function (k) {
      svg.appendChild(svgEl('ellipse', {
        cx: k[0], cy: k[1], rx: '5', ry: '9.5', transform: 'rotate(' + k[2] + ' ' + k[0] + ' ' + k[1] + ')',
        fill: 'currentColor', stroke: 'none'
      }));
    });
    wrap.appendChild(svg);
    return wrap;
  }

  // neutral inline "sketch pending" line-art mark — used when art[zone] url is null.
  // deliberately generic (a loose framed contour), so a missing generation never leaves the
  // zone empty and never shows a broken <img>. drawn with currentColor so substrate ink applies.
  /** @returns {Element} */
  function makePlaceholderArt() {
    var svg = svgEl('svg', {
      class: 'rc-artzone__art', viewBox: '0 0 300 150',
      role: 'presentation', focusable: 'false', 'aria-hidden': 'true'
    });
    // soft rounded frame
    svg.appendChild(svgEl('path', {
      d: 'M40 40 C40 30 50 26 66 26 L234 26 C250 26 260 30 260 42 L260 108 C260 120 250 124 234 124 L66 124 C50 124 40 120 40 110 Z',
      fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6', 'stroke-opacity': '.55'
    }));
    // a loose hand-drawn swoosh suggesting a pending sketch
    svg.appendChild(svgEl('path', {
      d: 'M78 96 C104 60 140 60 166 84 C186 102 214 96 226 66',
      fill: 'none', stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-opacity': '.5'
    }));
    // three stipple dots
    ['112', '150', '190'].forEach(function (cx, i) {
      svg.appendChild(svgEl('circle', { cx: cx, cy: (i === 1 ? '54' : '60'), r: '1.4', fill: 'currentColor', 'fill-opacity': '.5' }));
    });
    return svg;
  }

  // request body for one lazy art-zone generation. pure: id + zone in, mode body out.
  // tested via window.KODIAK_recipeArtBody.
  /**
   * @param {string|null} recipeId
   * @param {string} artKey
   * @returns {{mode: string, recipe_id: string, zone: string}|null}
   */
  function recipeArtBody(recipeId, artKey) {
    var id = (recipeId == null) ? '' : String(recipeId).trim();
    if (!id) return null;
    return { mode: 'recipe-art', recipe_id: id, zone: artKey };
  }
  try { window.KODIAK_recipeArtBody = recipeArtBody; } catch (e) {}
  /** @type {string} */
  var ART_GEN_STATUS = 'generating image using SDXL on Amazon Bedrock';
  // one in-flight generation per zone node — a re-observed node never double-fires.
  /**
   * @param {unknown} recipeId
   * @param {unknown} artKey
   */
  function artGenKey(recipeId, artKey) { return String(recipeId) + '|' + String(artKey); }
  /** @type {Object<string, boolean>} */
  var artGenFired = {};
  // swap a skeleton+status pair for the generated image. failure keeps the
  // placeholder: a missing drawing is never an error on the card face.
  /**
   * @param {HTMLElement} wrap
   * @param {string} recipeId
   * @param {string} artKey
   */
  function fireArtGen(wrap, recipeId, artKey) {
    var key = artGenKey(recipeId, artKey);
    if (artGenFired[key]) return;
    artGenFired[key] = true;
    var body = recipeArtBody(recipeId, artKey);
    if (!body) return;
    fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (resp) { return resp.json(); }).then(function (json) {
      if (!json || json.ok !== true || !json.url) throw new Error('no-url');
      var img = document.createElement('img');
      img.setAttribute('class', 'rc-artzone__art');
      img.setAttribute('src', String(json.url));
      img.setAttribute('alt', '');
      img.setAttribute('loading', 'eager');
      img.setAttribute('aria-hidden', 'true');
      img.addEventListener('error', function () {
        if (img.parentNode) { img.parentNode.replaceChild(makePlaceholderArt(), img); }
      });
      var skel = wrap.querySelector('.rc-artzone__skeleton');
      if (skel) { wrap.replaceChild(img, skel); }
      var st = wrap.querySelector('.rc-art-status');
      if (st && st.parentNode) { st.parentNode.removeChild(st); }
    }).catch(function () {
      var skel = wrap.querySelector('.rc-artzone__skeleton');
      if (skel) { wrap.replaceChild(makePlaceholderArt(), skel); }
      var st = wrap.querySelector('.rc-art-status');
      if (st && st.parentNode) { st.parentNode.removeChild(st); }
    });
  }
  // observe one skeleton zone: generation fires only when it scrolls into
  // view, so below-fold zones cost zero requests until seen. no
  // IntersectionObserver (old browser, tests) degrades to immediate fetch.
  /**
   * @param {HTMLElement} wrap
   * @param {string} recipeId
   * @param {string} artKey
   */
  function observeArtZone(wrap, recipeId, artKey) {
    if (typeof IntersectionObserver === 'undefined') { fireArtGen(wrap, recipeId, artKey); return; }
    var seen = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { seen.disconnect(); fireArtGen(wrap, recipeId, artKey); }
      });
    }, { rootMargin: '200px' });
    seen.observe(wrap);
  }
  // one art zone: white base coat + (real image OR lazy-generate skeleton OR
  // placeholder svg). never empty. gen carries {recipeId} when the card names
  // a catalog recipe and the zone has no URL yet — those zones generate on
  // scroll instead of showing the pending mark.
  /**
   * @param {{css: string, dataZone: string, artKey: string}} zone
   * @param {string|null} artUrl
   * @param {{recipeId: string|null}|null} gen
   * @returns {HTMLElement}
   */
  function makeArtZone(zone, artUrl, gen) {
    var wrap = el('div', 'rc-artzone ' + zone.css);
    wrap.setAttribute('data-zone', zone.dataZone);
    var base = el('div', 'rc-artzone__base');                  // white base coat behind the art
    base.setAttribute('aria-hidden', 'true');
    wrap.appendChild(base);
    if (artUrl != null && String(artUrl).trim().length) {
      var img = el('img', 'rc-artzone__art');
      img.setAttribute('src', String(artUrl));
      img.setAttribute('alt', '');
      img.setAttribute('loading', 'eager');
      img.setAttribute('aria-hidden', 'true');
      // if a presigned url has expired or fails, swap in the placeholder rather than a broken image.
      img.addEventListener('error', function () {
        if (img.parentNode) { img.parentNode.replaceChild(makePlaceholderArt(), img); }
      });
      wrap.appendChild(img);
    } else if (gen && gen.recipeId) {
      var skel = el('div', 'rc-artzone__art rc-artzone__skeleton');
      skel.setAttribute('aria-hidden', 'true');
      wrap.appendChild(skel);
      var st = el('div', 'rc-art-status', ART_GEN_STATUS);
      st.setAttribute('aria-hidden', 'true');
      wrap.appendChild(st);
      observeArtZone(wrap, gen.recipeId, zone.artKey);
    } else {
      wrap.appendChild(makePlaceholderArt());
    }
    return wrap;
  }

  // wrap the leading verb of a step in <b class="rc-step-verb">. if the step already starts with
  // an ALLCAPS token, wrap that token as-is; otherwise wrap the first word, uppercased.
  /**
   * @param {unknown} step
   * @returns {HTMLLIElement}
   */
  function makeStepLi(step) {
    var li = document.createElement('li');
    var text = String(step == null ? '' : step).trim();
    if (!text) { return li; }
    var m = text.match(/^(\S+)(\s+[\s\S]*)?$/);
    if (!m) { li.textContent = text; return li; }
    var first = m[1];
    var rest = m[2] || '';
    var verb = el('b', 'rc-step-verb');
    // ALLCAPS if the word (stripped of trailing punctuation) is already uppercase letters.
    var core = first.replace(/[^A-Za-z]/g, '');
    var isAllCaps = core.length > 0 && core === core.toUpperCase();
    verb.textContent = isAllCaps ? first : first.toUpperCase();
    li.appendChild(verb);
    if (rest) { li.appendChild(document.createTextNode(rest)); }
    return li;
  }

  // a full recipe card node built to the exact design-standard structure.
  /**
   * @param {MonthCard} card
   * @returns {HTMLElement}
   */
  function buildRecipeCard(card) {
    var rc = el('div', 'rc-card');
    rc.setAttribute('data-substrate', card.substrate || 'kraft');
    rc.setAttribute('role', 'img');
    rc.setAttribute('aria-label', 'Recipe card: ' + (card.title || 'recipe') + ' (' + (card.market || '') + ' ' + (card.month || '') + ')');

    // header: corner + title + corner
    var header = el('header', 'rc-header');
    header.appendChild(makeCorner('left'));
    header.appendChild(el('h3', 'rc-title', card.title || (card.recipe && card.recipe.name) || 'recipe'));
    header.appendChild(makeCorner('right'));
    rc.appendChild(header);

    // meta bar: 4 cells, null -> em-dash
    var meta = el('div', 'rc-meta');
    meta.setAttribute('data-zone', 'metadata_strip');
    // missing meta is an empty map, not a guess — every field stays optional.
    var m = card.meta || /** @type {Object<string, string>} */ ({});
    META_CELLS.forEach(function (cell) {
      var c = el('div', 'rc-meta__cell');
      c.appendChild(el('span', 'rc-meta__value', orDash(m[cell.key])));
      var label = (card.metaLabels && card.metaLabels[cell.key]) || cell.label;
      c.appendChild(el('span', 'rc-meta__label', label));
      meta.appendChild(c);
    });
    rc.appendChild(meta);

    // two-column body
    var cols = el('div', 'rc-columns');

    // left: ingredients + raw art + optional seasonal tip
    var left = el('section', 'recipe-card-column recipe-card-ingredients');
    left.appendChild(el('h4', 'rc-col-heading',
      (card.colLabels && card.colLabels.ingredients) || 'ingredients'));
    var ul = el('ul', 'rc-ingredients');
    // missing art is an empty RecipeArt — all three zones optional, so the cast is total.
    // gen carries the catalog recipe id so empty zones lazy-generate on scroll
    // instead of sitting on the pending mark; cards without a recipe id keep it.
    var art = card.art || /** @type {RecipeArt} */ ({});
    var gen = (card.recipe && card.recipe.id) ? { recipeId: String(card.recipe.id) } : null;
    (card.ingredients || []).forEach(function (ing) {
      var li = el('li', 'rc-ing');
      li.appendChild(el('span', 'rc-ing__name', (ing && ing.qty_name) ? String(ing.qty_name) : ''));
      // price: real value, or de-emphasized em-dash when null. never $0.00, never fabricated.
      var priceText = (ing && ing.price != null && String(ing.price).trim().length) ? String(ing.price) : EM_DASH;
      li.appendChild(el('span', 'rc-ing__price', priceText));
      ul.appendChild(li);
    });
    left.appendChild(ul);
    left.appendChild(makeArtZone(ART_ZONES[0], art[ART_ZONES[0].artKey] || null, gen));
    cols.appendChild(left);

    // right: technique drawing first, then the steps heading + list, then
    // the finished drawing: the column reads top-to-bottom as see-make-plate.
    var right = el('section', 'recipe-card-column recipe-card-execution');
    right.appendChild(makeArtZone(ART_ZONES[1], art[ART_ZONES[1].artKey] || null, gen));
    right.appendChild(el('h4', 'rc-col-heading',
      (card.colLabels && card.colLabels.steps) || 'steps'));
    var ol = el('ol', 'rc-steps');
    (card.steps || []).forEach(function (step) { ol.appendChild(makeStepLi(step)); });
    right.appendChild(ol);
    right.appendChild(makeArtZone(ART_ZONES[2], art[ART_ZONES[2].artKey] || null, gen));
    cols.appendChild(right);

    rc.appendChild(cols);
    return rc;
  }

  // honest empty-state card for months with no in-season local pick (ingredient null / reason set).
  // never fabricates a recipe. reuses the card shell + substrate so it sits cleanly in the gallery.
  /**
   * @param {MonthCard} card
   * @returns {HTMLElement}
   */
  function buildEmptyStateCard(card) {
    var rc = el('div', 'rc-card rc-card--empty');
    rc.setAttribute('data-substrate', card.substrate || 'kraft');
    rc.setAttribute('role', 'note');
    rc.setAttribute('aria-label', 'No in-season local pick for ' + (card.month || 'this month'));

    var header = el('header', 'rc-header');
    header.appendChild(makeCorner('left'));
    header.appendChild(el('h3', 'rc-title', 'no in-season pick'));
    header.appendChild(makeCorner('right'));
    rc.appendChild(header);

    var body = el('div', 'rc-empty-body');
    body.appendChild(el('p', 'rc-empty-lead', 'no in-season local pick for ' + (card.month || 'this month')));
    if (card.reason) { body.appendChild(el('p', 'rc-empty-reason', String(card.reason))); }
    rc.appendChild(body);
    return rc;
  }

  /**
   * @param {MonthCard} card
   * @returns {boolean}
   */
  function isEmptyState(card) {
    return !card || card.ingredient == null || card.reason != null;
  }

  // build one market's group: heading + a shell-wrapped card per month (sorted).
  /**
   * @param {string} market
   * @param {Object<string, MonthCard>} monthsObj
   * @returns {HTMLElement}
   */
  function buildMarketGroup(market, monthsObj) {
    var group = el('section', 'rc-gallery-group');
    group.setAttribute('aria-label', market);
    group.appendChild(el('h3', 'rc-gallery-market', market));

    var grid = el('div', 'rc-gallery-grid');
    Object.keys(monthsObj).sort().forEach(function (month) {
      var card = monthsObj[month] || {};
      var shell = el('div', 'rc-card-shell');
      var node = isEmptyState(card) ? buildEmptyStateCard(card) : buildRecipeCard(card);
      shell.appendChild(node);
      var cell = el('div', 'rc-gallery-cell');
      cell.appendChild(el('div', 'rc-gallery-month', month));
      cell.appendChild(shell);
      grid.appendChild(cell);
    });
    group.appendChild(grid);
    return group;
  }

  // month name ("September") -> card month key ("2026-09"). seasons and
  // holidays have no card keys in the dataset (12 month keys only), so they
  // resolve to null and the gallery says so honestly instead of guessing.
  /** @type {Object<string, string>} */
  var MONTH_TO_KEY = {january: '2026-01', february: '2026-02',
    march: '2026-03', april: '2026-04', may: '2026-05', june: '2026-06',
    july: '2026-07', august: '2026-08', september: '2026-09',
    october: '2026-10', november: '2026-11', december: '2026-12'};

  // the gallery shows ONE market group for the pipeline's selected market,
  // not the whole book: market code (#locality) -> frontier card key via
  // the marketFeaturedFrontier map owned by data-core.js.
  /**
   * @returns {string|null}
   */
  function selectedCardMarket() {
    var data = window.KODIAK_RECIPE_CARDS;
    if (!data || typeof data !== 'object') return null;
    var sel = null;
    try { sel = /** @type {HTMLInputElement|null} */ (document.getElementById('locality')); } catch (e) { sel = null; }
    var code = (sel && sel.value) ? String(sel.value) : '';
    if (code && data[code]) return code;   // select already holds a card key
    var map = (typeof marketFeaturedFrontier !== 'undefined') ? marketFeaturedFrontier : {};
    var key = (code && map[code]) ? map[code] : null;
    if (key && data[key]) return key;
    return null;
  }

  /**
   * @returns {string|null}
   */
  function selectedMonthKey() {
    var s = null;
    try { s = /** @type {HTMLInputElement|null} */ (document.getElementById('seasonalSelect')); } catch (e) { s = null; }
    var v = (s && s.value) ? String(s.value).trim().toLowerCase() : '';
    if (!v) return '';   // "Season: any" — no month filter
    if (MONTH_TO_KEY[v]) return MONTH_TO_KEY[v];
    // seasons/holidays resolve to their representative month card via the
    // shared data-core.js map — a Halloween pick shows the October card.
    try{
      var numFn = (typeof window !== 'undefined') ? window.KODIAK_frontierMonthNum : null;
      if(typeof numFn === 'function'){
        var n = numFn(v);
        if(n) return '2026-' + (n < 10 ? '0' : '') + n;
      }
    }catch(e){}
    return null;   // unknown value — no such cards
  }

  function renderGallery() {
    var mount = document.getElementById('recipesGallery');
    if (!mount) return;   // surface not present — no-op
    var body = mount.querySelector('.rc-gallery-body') || mount;
    body.innerHTML = '';

    var data = window.KODIAK_RECIPE_CARDS;
    if (!data || typeof data !== 'object' || !Object.keys(data).length) {
      var empty = el('p', 'rc-gallery-empty', 'Recipe cards will appear here once generated.');
      body.appendChild(empty);
      return;
    }

    var market = selectedCardMarket();
    if (!market) {
      body.appendChild(el('p', 'rc-gallery-empty',
        'No recipe cards for the selected market yet — pick a market with a frontier card.'));
      return;
    }
    /** @type {Object<string, MonthCard>} */
    var monthsObj = data[market] || {};
    var monthKey = selectedMonthKey();
    if (monthKey === null) {
      body.appendChild(el('p', 'rc-gallery-empty',
        'No card for this market and season yet.'));
      return;
    }
    /** @type {Object<string, MonthCard>} */
    var filtered = {};
    if (!monthKey) {
      filtered = monthsObj;   // "Season: any" — this market's full year
    } else if (monthsObj[monthKey]) {
      filtered[monthKey] = monthsObj[monthKey];
    }
    if (!Object.keys(filtered).length) {
      body.appendChild(el('p', 'rc-gallery-empty',
        'No card for this market and month yet.'));
      return;
    }
    body.appendChild(buildMarketGroup(market, filtered));
  }

  function bindGalleryRefresh() {
    // #locality changes fire from the select, the listbox picker, and
    // restores — listen at document level so all of them re-render.
    document.addEventListener('change', function (e) {
      // EventTarget carries no id — narrow to Element before reading it.
      var t = /** @type {Element|null} */ (e.target);
      if (t && (t.id === 'locality' || t.id === 'seasonalSelect')) {
        previewLang = 'en';   // new market/month starts in English
        renderPreviewCard();
      }
    });
  }

  // Preview language toggle — baked translations only (window.KODIAK_RECIPE_I18N,
  // recipe-i18n-data.js). No live endpoint: the toggle swaps title, ingredient
  // names, and steps from the baked per-language entry and badges the card as
  // machine-translated. Prices, art, and meta never translate.
  var previewLang = 'en';
  /** @type {Object<string, string>} */
  var LANG_NAMES = { es: 'Español', pt: 'Português', fr: 'Français', ar: 'العربية',
    de: 'Deutsch', zh: '中文', vi: 'Tiếng Việt', ko: '한국어', ht: 'Kreyòl',
    tl: 'Tagalog', ja: '日本語', so: 'Soomaali', pl: 'polski', ru: 'русский',
    am: 'አማርኛ', ilo: 'Ilocano', hmn: 'Hmoob', bs: 'bosanski', nv: 'Diné',
    ne: 'नेपाली', my: 'မြန်မာ' };
  /**
   * @param {string} code
   * @returns {string}
   */
  function langName(code) { return LANG_NAMES[code] || code; }

  /**
   * @param {string} market
   * @param {string} monthKey
   * @returns {Object<string, I18nEntry>}
   */
  function previewLangsFor(market, monthKey) {
    var book = window.KODIAK_RECIPE_I18N;
    if (!book || typeof book !== 'object') return {};
    var byMarket = book[market] || {};
    var byMonth = byMarket[monthKey] || {};
    return (byMonth && typeof byMonth === 'object') ? byMonth : {};
  }

  /**
   * @param {MonthCard} card
   * @param {string} lang
   * @param {I18nEntry|null|undefined} entry
   * @returns {{card: MonthCard, translated: TranslationProvenance|null}}
   */
  function withPreviewLang(card, lang, entry) {
    if (!lang || lang === 'en' || !entry) return { card: card, translated: null };
    // shallow copy, same runtime shape as Object.assign — card keeps its type.
    var c = /** @type {MonthCard} */ (Object.assign({}, card));
    if (entry.title) c.title = entry.title;
    if (entry.ingredients) c.ingredients = entry.ingredients;
    if (entry.steps) c.steps = entry.steps;
    // meta bar: translated prep/cook/serves values ride on the entry;
    // est_cost is a universal figure and stays. Labels come from the baked
    // per-language table; missing labels fall back to English in the render.
    if (entry.meta) {
      /** @type {Object<string, string>} */
      var m = {};
      var srcMeta = card.meta || /** @type {Object<string, string>} */ ({});
      Object.keys(srcMeta).forEach(function (k) { m[k] = srcMeta[k]; });
      ['prep', 'cook', 'serves'].forEach(function (k) {
        var mv = entry.meta ? entry.meta[k] : undefined;
        if (mv) m[k] = mv;
      });
      c.meta = m;
      var labelTable = /** @type {Object<string, Object<string, string>>} */ (
        window.KODIAK_RECIPE_META_LABELS || {});
      if (labelTable[lang]) {
        c.metaLabels = labelTable[lang];
        c.colLabels = labelTable[lang];
      }
    }
    return { card: c, translated: entry.translation || null };
  }

  /**
   * @param {string[]} codes
   * @param {string} active
   * @param {(code: string) => void} onPick
   * @returns {HTMLElement}
   */
  function buildLangToggle(codes, active, onPick) {
    var row = el('div', 'rc-lang-toggle');
    row.setAttribute('role', 'group');
    row.setAttribute('aria-label', 'Preview language');
    ['en'].concat(codes).forEach(function (code) {
      var b = el('button', 'rc-lang-toggle__btn' + (code === active ? ' is-active' : ''),
        code === 'en' ? 'English' : langName(code));
      b.setAttribute('type', 'button');
      b.setAttribute('aria-pressed', code === active ? 'true' : 'false');
      b.setAttribute('data-lang', code);
      b.addEventListener('click', function () { onPick(code); });
      row.appendChild(b);
    });
    return row;
  }

  /**
   * @param {TranslationProvenance|null} prov
   * @returns {HTMLElement}
   */
  function buildTranslationBadge(prov) {
    var text = 'machine translated · not human reviewed';
    if (prov && prov.allergen_fallback_lines && prov.allergen_fallback_lines.length) {
      text += ' · ' + prov.allergen_fallback_lines.length + ' line' +
        (prov.allergen_fallback_lines.length === 1 ? '' : 's') + ' kept in English';
    }
    var badge = el('p', 'rc-lang-badge', text);
    return badge;
  }

  // one card for the preview: the selected market's card for the selected
  // month. "Season: any" and missing months fall back to the current
  // calendar month so the preview always shows exactly one card.
  // seasons/holidays have no card keys — honest empty state, never a guess.
  /** @returns {string} */
  function currentMonthKey() {
    return MONTH_TO_KEY[['january', 'february', 'march', 'april', 'may', 'june',
      'july', 'august', 'september', 'october', 'november',
      'december'][new Date().getMonth()]];
  }

  function renderPreviewCard() {
    var slot = document.getElementById('previewRecipe');
    if (!slot) { renderGallery(); return; }   // old markup fallback
    slot.innerHTML = '';

    var data = window.KODIAK_RECIPE_CARDS;
    if (!data || typeof data !== 'object' || !Object.keys(data).length) {
      slot.appendChild(el('p', 'rc-gallery-empty', 'Recipe card will appear here once generated.'));
      dockPreviewLangToggle(null);
      return;
    }

    var market = selectedCardMarket();
    if (!market) {
      slot.appendChild(el('p', 'rc-gallery-empty',
        'No recipe card for the selected market yet.'));
      dockPreviewLangToggle(null);
      return;
    }
    /** @type {Object<string, MonthCard>} */
    var monthsObj = data[market] || {};
    var monthKey = selectedMonthKey();
    if (!monthKey) monthKey = currentMonthKey();   // "any" or holiday -> this month
    var card = monthsObj[monthKey];
    if (!card) {
      slot.appendChild(el('p', 'rc-gallery-empty',
        'No card for this market and month yet.'));
      dockPreviewLangToggle(null);
      return;
    }
    // column wrap: #previewRecipe is a full-width block, so the toggle,
    // badge, and shell stack in their own column inside it.
    var wrap = el('div', 'rc-preview-wrap');
    var shell = el('div', 'rc-card-shell');
    if (isEmptyState(card)) {
      previewLang = 'en';
      shell.appendChild(buildEmptyStateCard(card));
    } else {
      var monthLangs = previewLangsFor(market, monthKey);
      var codes = Object.keys(monthLangs);
      if (previewLang !== 'en' && !monthLangs[previewLang]) previewLang = 'en';
      var applied = withPreviewLang(card, previewLang, monthLangs[previewLang]);
      if (codes.length) {
        wrap.appendChild(buildLangToggle(codes, previewLang, function (code) {
          previewLang = code;
          renderPreviewCard();
        }));
        if (applied.translated) wrap.appendChild(buildTranslationBadge(applied.translated));
      }
      shell.appendChild(buildRecipeCard(applied.card));
    }
    wrap.appendChild(shell);
    slot.appendChild(wrap);
    dockPreviewLangToggle(wrap);
  }

  // Output-header language dock: the recipe toggle lives beside the publish
  // targets (with its own label) instead of floating between copy and card.
  // The node is MOVED, not cloned, so its listeners survive; a render with no
  // languages hides the dock instead of leaving a stale toggle behind.
  /**
   * @param {HTMLElement|null} scope
   * @returns {void}
   */
  function dockPreviewLangToggle(scope) {
    var pub = document.getElementById('publishTargets');
    if (!pub) return;
    var line = document.getElementById('outputLangLine');
    if (!line) {
      line = document.createElement('span');
      line.id = 'outputLangLine';
      line.className = 'ff-output-langline';
      var label = document.createElement('span');
      label.className = 'ff-output-langline__label';
      label.textContent = 'Localization';
      line.appendChild(label);
      pub.appendChild(line);
    }
    var toggle = scope ? scope.querySelector('.rc-lang-toggle') : null;
    if (toggle) {
      line.appendChild(toggle);
      line.hidden = false;
    } else {
      line.hidden = true;
    }
  }

  function bindPreviewRefresh() {
    // #locality changes fire from the select, the listbox picker, and
    // restores — listen at document level so all of them re-render.
    document.addEventListener('change', function (e) {
      // EventTarget carries no id — narrow to Element before reading it.
      var t = /** @type {Element|null} */ (e.target);
      if (t && (t.id === 'locality' || t.id === 'seasonalSelect')) {
        renderPreviewCard();
      }
    });
  }

  // expose for manual re-render / tests
  window.KODIAK_renderRecipeGallery = renderGallery;
  window.KODIAK_renderPreviewCard = renderPreviewCard;

  // bootstrap last: every declaration above (including the preview-language
  // toggle state) is initialized before the first render runs.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { bindGalleryRefresh(); renderPreviewCard(); });
  } else {
    bindGalleryRefresh();
    renderPreviewCard();
  }
})();
