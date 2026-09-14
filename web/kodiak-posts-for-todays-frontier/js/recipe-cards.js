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
  var CORNER_LEFT = 'M8 78 C22 60 20 34 44 24 M44 24 C40 34 48 40 58 38 M44 24 C50 30 50 44 46 52';
  var CORNER_RIGHT = 'M92 78 C78 60 80 34 56 24 M56 24 C60 34 52 40 42 38 M56 24 C50 30 50 44 54 52';
  var CORNER_RULE = 'M16 84 L84 84';

  // the three artzone divs, in render order, each mapped to its data key + css modifier + data-zone.
  var ART_ZONES = [
    { css: 'rc-artzone--raw', dataZone: 'raw_ingredient_sketch', artKey: 'raw_ingredient' },
    { css: 'rc-artzone--technique', dataZone: 'technique_sketch', artKey: 'technique' },
    { css: 'rc-artzone--plate', dataZone: 'finished_plate_sketch', artKey: 'finished_plate' }
  ];

  var META_CELLS = [
    { key: 'prep', label: 'Prep' },
    { key: 'cook', label: 'Cook' },
    { key: 'serves', label: 'Serves' },
    { key: 'est_cost', label: 'Est cost' }
  ];

  var EM_DASH = '\u2014';

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function svgEl(tag, attrs) {
    var node = document.createElementNS(SVGNS, tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    }
    return node;
  }

  // present a value or an honest em-dash when null/empty. never fabricates.
  function orDash(v) {
    if (v == null) return EM_DASH;
    var s = String(v).trim();
    return s.length ? s : EM_DASH;
  }

  // corner accent svg — identical for every card (static flourish, matches specimen).
  function makeCorner(side) {
    var wrap = el('div', 'rc-corner rc-corner--' + side);
    wrap.setAttribute('data-zone', side === 'left' ? 'corner_accent_left' : 'corner_accent_right');
    wrap.setAttribute('aria-hidden', 'true');
    var svg = svgEl('svg', { viewBox: '0 0 100 100', class: 'rc-corner__art', role: 'presentation', focusable: 'false' });
    svg.appendChild(svgEl('path', {
      d: side === 'left' ? CORNER_LEFT : CORNER_RIGHT,
      fill: 'none', stroke: 'currentColor', 'stroke-width': '2.2', 'stroke-linecap': 'round'
    }));
    svg.appendChild(svgEl('path', {
      d: CORNER_RULE, fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6', 'stroke-linecap': 'round'
    }));
    wrap.appendChild(svg);
    return wrap;
  }

  // neutral inline "sketch pending" line-art mark — used when art[zone] url is null.
  // deliberately generic (a loose framed contour), so a missing generation never leaves the
  // zone empty and never shows a broken <img>. drawn with currentColor so substrate ink applies.
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

  // one art zone: white base coat + (real image OR placeholder svg). never empty.
  function makeArtZone(zone, artUrl) {
    var wrap = el('div', 'rc-artzone ' + zone.css);
    wrap.setAttribute('data-zone', zone.dataZone);
    wrap.appendChild(el('div', 'rc-artzone__base'));           // white base coat behind the art
    wrap.lastChild.setAttribute('aria-hidden', 'true');
    if (artUrl != null && String(artUrl).trim().length) {
      var img = el('img', 'rc-artzone__art');
      img.setAttribute('src', String(artUrl));
      img.setAttribute('alt', '');
      img.setAttribute('loading', 'lazy');
      img.setAttribute('aria-hidden', 'true');
      // if a presigned url has expired or fails, swap in the placeholder rather than a broken image.
      img.addEventListener('error', function () {
        if (img.parentNode) { img.parentNode.replaceChild(makePlaceholderArt(), img); }
      });
      wrap.appendChild(img);
    } else {
      wrap.appendChild(makePlaceholderArt());
    }
    return wrap;
  }

  // wrap the leading verb of a step in <b class="rc-step-verb">. if the step already starts with
  // an ALLCAPS token, wrap that token as-is; otherwise wrap the first word, uppercased.
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

  // pull a short, tasteful context line from seasonal_moment without cluttering the face.
  // seasonal_moment may be a list of moment objects or null. take the highest-signal moment
  // (first confirmed, else first) and name it. no [S]/[~]/[?] provenance noise.
  function seasonalLine(seasonalMoment) {
    if (!Array.isArray(seasonalMoment) || !seasonalMoment.length) return null;
    var pick = null;
    for (var i = 0; i < seasonalMoment.length; i++) {
      var mm = seasonalMoment[i];
      if (mm && mm.status === 'confirmed') { pick = mm; break; }
    }
    if (!pick) pick = seasonalMoment[0];
    if (!pick || !pick.moment) return null;
    return String(pick.moment).trim() || null;
  }

  // a full recipe card node built to the exact design-standard structure.
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
    var m = card.meta || {};
    META_CELLS.forEach(function (cell) {
      var c = el('div', 'rc-meta__cell');
      c.appendChild(el('span', 'rc-meta__value', orDash(m[cell.key])));
      c.appendChild(el('span', 'rc-meta__label', cell.label));
      meta.appendChild(c);
    });
    rc.appendChild(meta);

    // two-column body
    var cols = el('div', 'rc-columns');

    // left: ingredients + raw art + optional seasonal tip
    var left = el('section', 'recipe-card-column recipe-card-ingredients');
    left.appendChild(el('h4', 'rc-col-heading', 'ingredients'));
    var ul = el('ul', 'rc-ingredients');
    (card.ingredients || []).forEach(function (ing) {
      var li = el('li', 'rc-ing');
      li.appendChild(el('span', 'rc-ing__name', (ing && ing.qty_name) ? String(ing.qty_name) : ''));
      // price: real value, or de-emphasized em-dash when null. never $0.00, never fabricated.
      var priceText = (ing && ing.price != null && String(ing.price).trim().length) ? String(ing.price) : EM_DASH;
      li.appendChild(el('span', 'rc-ing__price', priceText));
      ul.appendChild(li);
    });
    left.appendChild(ul);
    left.appendChild(makeArtZone(ART_ZONES[0], (card.art || {})[ART_ZONES[0].artKey]));
    var moment = seasonalLine(card.seasonal_moment);
    if (moment) {
      var tip = el('p', 'rc-tip');
      tip.appendChild(el('span', 'rc-tip__label', 'in season'));
      tip.appendChild(document.createTextNode(' ' + moment));
      left.appendChild(tip);
    }
    cols.appendChild(left);

    // right: steps + technique art + plate art
    var right = el('section', 'recipe-card-column recipe-card-execution');
    right.appendChild(el('h4', 'rc-col-heading', 'steps'));
    var ol = el('ol', 'rc-steps');
    (card.steps || []).forEach(function (step) { ol.appendChild(makeStepLi(step)); });
    right.appendChild(ol);
    right.appendChild(makeArtZone(ART_ZONES[1], (card.art || {})[ART_ZONES[1].artKey]));
    right.appendChild(makeArtZone(ART_ZONES[2], (card.art || {})[ART_ZONES[2].artKey]));
    cols.appendChild(right);

    rc.appendChild(cols);
    return rc;
  }

  // honest empty-state card for months with no in-season local pick (ingredient null / reason set).
  // never fabricates a recipe. reuses the card shell + substrate so it sits cleanly in the gallery.
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

  function isEmptyState(card) {
    return !card || card.ingredient == null || card.reason != null;
  }

  // build one market's group: heading + a shell-wrapped card per month (sorted).
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

    Object.keys(data).sort().forEach(function (market) {
      var monthsObj = data[market];
      if (monthsObj && typeof monthsObj === 'object' && Object.keys(monthsObj).length) {
        body.appendChild(buildMarketGroup(market, monthsObj));
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderGallery);
  } else {
    renderGallery();
  }

  // expose for manual re-render / tests
  window.KODIAK_renderRecipeGallery = renderGallery;
})();
