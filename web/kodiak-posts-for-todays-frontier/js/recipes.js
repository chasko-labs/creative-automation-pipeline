// Recipes brainstorm renderer — visual overview, NOT a pipeline step.
// Reads window.KODIAK_RECIPE_CARDS (same card-data shape as the main page,
// loaded by js/recipe-cards-data.js) + window.KODIAK_FRONTIER_PAIRS /
// window.KODIAK_MARKET_PLACES (js/recipes-frontier-pairs.js) and builds three
// sections: (1) full market x 12-month ingredient matrix, (2) metro ->
// frontier pairing panels, (3) ingredient -> recipe sample cards.
//
// The sample cards reuse the .rc-card component class structure from the
// Design System Inventory specimen (details.html #recipe-card-standard) and
// the main-page renderer (js/recipe-cards.js) verbatim, so they share looks
// AND data shapes. Art zones show the card's finished drawing where one
// exists, otherwise a neutral inline stand-in sketch — this page never
// fetches remote art. Never throws when data is absent.
(function () {
  'use strict';

  var SVGNS = 'http://www.w3.org/2000/svg';
  var EM_DASH = '\u2014';

  // Calendar months in order — months are the source of truth; the season on
  // each entry is the reading aid (spring Mar-May, summer Jun-Aug,
  // fall Sep-Nov, winter Dec-Feb).
  /** @type {MonthEntry[]} */
  var MONTHS = [
    { key: '2026-01', name: 'January', short: 'Jan', season: 'winter' },
    { key: '2026-02', name: 'February', short: 'Feb', season: 'winter' },
    { key: '2026-03', name: 'March', short: 'Mar', season: 'spring' },
    { key: '2026-04', name: 'April', short: 'Apr', season: 'spring' },
    { key: '2026-05', name: 'May', short: 'May', season: 'spring' },
    { key: '2026-06', name: 'June', short: 'Jun', season: 'summer' },
    { key: '2026-07', name: 'July', short: 'Jul', season: 'summer' },
    { key: '2026-08', name: 'August', short: 'Aug', season: 'summer' },
    { key: '2026-09', name: 'September', short: 'Sep', season: 'fall' },
    { key: '2026-10', name: 'October', short: 'Oct', season: 'fall' },
    { key: '2026-11', name: 'November', short: 'Nov', season: 'fall' },
    { key: '2026-12', name: 'December', short: 'Dec', season: 'winter' }
  ];

  // Static corner flourish paths, lifted from the specimen (left + right
  // mirror) — identical for every card, matches design standard.
  // wheat ear corner mark: curved stem, filled kernel ellipses alternating along
  // it, three awns off the tip. filled grain reads at 1in size; no underline
  // rule — the ear stands on its own.
  var CORNER_STEM_LEFT = 'M20 94 C28 66 32 44 42 14';
  var CORNER_STEM_RIGHT = 'M80 94 C72 66 68 44 58 14';
  var CORNER_AWNS_LEFT = 'M42 14 L35 1 M42 14 L43 0 M42 14 L49 2';
  var CORNER_AWNS_RIGHT = 'M58 14 L65 1 M58 14 L57 0 M58 14 L51 2';
  // kernel triples are [x, y, rotation] — a tuple, not number[].
  /** @type {Array<[number, number, number]>} */
  var CORNER_KERNELS_LEFT = [[33,24,-25],[46,28,25],[30,36,-25],[43,40,25],[28,48,-22],[40,52,22],[26,60,-20],[37,64,20],[25,72,-15],[34,74,15]];
  /** @type {Array<[number, number, number]>} */
  var CORNER_KERNELS_RIGHT = [[67,24,25],[54,28,-25],[70,36,25],[57,40,-25],[72,48,22],[60,52,-22],[74,60,20],[63,64,-20],[75,72,15],[66,74,-15]];

  /** @type {{css: string, dataZone: string}[]} */
  var ART_ZONES = [
    { css: 'rc-artzone--raw', dataZone: 'raw_ingredient_sketch' },
    { css: 'rc-artzone--technique', dataZone: 'technique_sketch' },
    { css: 'rc-artzone--plate', dataZone: 'finished_plate_sketch' }
  ];

  /** @type {{key: string, label: string}[]} */
  var META_CELLS = [
    { key: 'prep', label: 'Prep' },
    { key: 'cook', label: 'Cook' },
    { key: 'serves', label: 'Serves' },
    { key: 'est_cost', label: 'Est cost' }
  ];

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

  /**
   * @param {unknown} v
   * @returns {string}
   */
  function orDash(v) {
    if (v == null) return EM_DASH;
    var s = String(v).trim();
    return s.length ? s : EM_DASH;
  }

  /**
   * @param {string} market
   * @returns {string}
   */
  function placeFor(market) {
    var map = window.KODIAK_MARKET_PLACES || {};
    return map[market] || market;
  }

  // ---- shared art-thumb: neutral inline stand-in line-art mark ----
  // Deliberately generic so a sample card never shows an empty box or a
  // remote fetch. Drawn with currentColor so the card substrate ink applies.
  /** @returns {Element} */
  function makeArtThumb() {
    var svg = svgEl('svg', {
      class: 'rc-artzone__art art-thumb', viewBox: '0 0 300 150',
      role: 'presentation', focusable: 'false', 'aria-hidden': 'true'
    });
    svg.appendChild(svgEl('path', {
      d: 'M40 40 C40 30 50 26 66 26 L234 26 C250 26 260 30 260 42 L260 108 C260 120 250 124 234 124 L66 124 C50 124 40 120 40 110 Z',
      fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6', 'stroke-opacity': '.55'
    }));
    svg.appendChild(svgEl('path', {
      d: 'M78 96 C104 60 140 60 166 84 C186 102 214 96 226 66',
      fill: 'none', stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-opacity': '.5'
    }));
    ['112', '150', '190'].forEach(function (cx, i) {
      svg.appendChild(svgEl('circle', { cx: cx, cy: (i === 1 ? '54' : '60'), r: '1.4', fill: 'currentColor', 'fill-opacity': '.5' }));
    });
    return svg;
  }

  /**
   * @param {{css: string, dataZone: string}} zone
   * @param {string|null} url
   * @returns {HTMLElement}
   */
  function makeArtZone(zone, url) {
    var wrap = el('div', 'rc-artzone ' + zone.css);
    wrap.setAttribute('data-zone', zone.dataZone);
    var base = el('div', 'rc-artzone__base');
    base.setAttribute('aria-hidden', 'true');
    wrap.appendChild(base);
    if (url) {
      var img = document.createElement('img');
      img.setAttribute('class', 'rc-artzone__art rc-artimg');
      img.setAttribute('src', url);
      img.setAttribute('alt', '');
      img.setAttribute('aria-hidden', 'true');
      img.setAttribute('loading', 'lazy');
      wrap.appendChild(img);
    } else {
      wrap.appendChild(makeArtThumb());
    }
    return wrap;
  }

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

  /**
   * @param {unknown} step
   * @returns {HTMLLIElement}
   */
  function makeStepLi(step) {
    var li = document.createElement('li');
    var text = String(step == null ? '' : step).trim();
    if (!text) return li;
    var m = text.match(/^(\S+)(\s+[\s\S]*)?$/);
    if (!m) { li.textContent = text; return li; }
    var first = m[1];
    var rest = m[2] || '';
    var core = first.replace(/[^A-Za-z]/g, '');
    var verb = el('b', 'rc-step-verb', (core.length && core === core.toUpperCase()) ? first : first.toUpperCase());
    li.appendChild(verb);
    if (rest) li.appendChild(document.createTextNode(rest));
    return li;
  }


  // ---- section 1: full market x 12-month matrix ----
  function buildMatrix() {
    // const: the guard below narrows once and the narrowing survives into
    // the forEach closures (a var binding would forget it there).
    const mount = document.getElementById('rxMatrix');
    if (!mount) return;
    mount.innerHTML = '';
    var data = window.KODIAK_RECIPE_CARDS;
    if (!data || typeof data !== 'object' || !Object.keys(data).length) {
      mount.appendChild(el('p', 'rc-gallery-empty', 'Matrix will appear once card data loads.'));
      return;
    }
    // const keeps the guard above narrowed inside the forEach closures below.
    const book = data;
    var markets = Object.keys(data).sort(function (a, b) {
      return placeFor(a).localeCompare(placeFor(b));
    });

    var table = el('table', 'rx-matrix');
    table.setAttribute('aria-label', 'Every market by all 12 months, each cell naming its distinct in-season ingredient');
    var thead = document.createElement('thead');

    // Season reading-aid row: winter Jan-Feb | spring | summer | fall | winter Dec.
    var seasonRow = document.createElement('tr');
    seasonRow.appendChild(el('th', 'rx-matrix__corner', ''));
    // [season, colspan] pairs are tuples — positions have different meanings.
    /** @type {Array<[string, number]>} */
    var groups = [['winter', 2], ['spring', 3], ['summer', 3], ['fall', 3], ['winter', 1]];
    groups.forEach(function (g) {
      var th = el('th', 'rx-matrix__season season-cell season-cell--' + g[0], g[0]);
      th.setAttribute('colspan', String(g[1]));
      th.setAttribute('scope', 'colgroup');
      seasonRow.appendChild(th);
    });
    thead.appendChild(seasonRow);

    var monthRow = document.createElement('tr');
    var corner = el('th', 'rx-matrix__corner', 'market');
    corner.setAttribute('scope', 'col');
    monthRow.appendChild(corner);
    MONTHS.forEach(function (mo) {
      var th = el('th', 'rx-matrix__month', mo.short);
      th.setAttribute('scope', 'col');
      th.setAttribute('title', mo.name + ' (' + mo.season + ')');
      monthRow.appendChild(th);
    });
    thead.appendChild(monthRow);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    markets.forEach(function (market) {
      var tr = document.createElement('tr');
      tr.setAttribute('data-market', market);
      tr.setAttribute('data-place', placeFor(market).toLowerCase());
      var nameCell = el('th', 'market-cell', placeFor(market));
      nameCell.setAttribute('scope', 'row');
      nameCell.appendChild(el('span', 'market-cell__code', market));
      tr.appendChild(nameCell);
      /** @type {Object<string, MonthCard>} */
      var monthsObj = book[market] || {};
      MONTHS.forEach(function (mo) {
        /** @type {MonthCard} */
        var card = monthsObj[mo.key] || {};
        var td = el('td', 'season-cell season-cell--' + mo.season, orDash(card.ingredient));
        td.setAttribute('data-month', mo.key);
        td.setAttribute('title', placeFor(market) + ' — ' + mo.name + ': ' + orDash(card.ingredient));
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    mount.appendChild(table);

    var count = document.getElementById('rxMatrixCount');
    if (count) count.textContent = markets.length + ' markets × 12 months';
  }

  function bindMatrixFilter() {
    // narrowed once to HTMLInputElement with const, so the narrowing survives
    // into the event-listener closure below (var would forget it there).
    const input = /** @type {HTMLInputElement|null} */ (document.getElementById('rxMatrixFilter'));
    if (!input || input.dataset.bound) return;
    input.dataset.bound = '1';
    input.addEventListener('input', function () {
      var q = String(input.value || '').trim().toLowerCase();
      var rows = document.querySelectorAll('#rxMatrix tbody tr');
      var shown = 0;
      Array.prototype.forEach.call(rows, function (tr) {
        var hit = !q || (tr.getAttribute('data-place') || '').indexOf(q) !== -1 ||
          (tr.getAttribute('data-market') || '').toLowerCase().indexOf(q) !== -1;
        tr.style.display = hit ? '' : 'none';
        if (hit) shown++;
      });
      var count = document.getElementById('rxMatrixCount');
      if (count) count.textContent = shown + ' of ' + rows.length + ' markets × 12 months';
    });
  }

  // ---- section 2: metro -> frontier pairing panels ----
  function buildPairs() {
    const mount = document.getElementById('rxPairs');
    if (!mount) return;
    mount.innerHTML = '';
    var pairs = window.KODIAK_FRONTIER_PAIRS;
    if (!Array.isArray(pairs) || !pairs.length) {
      mount.appendChild(el('p', 'rc-gallery-empty', 'Pairings will appear once frontier data loads.'));
      return;
    }
    pairs.forEach(function (pair) {
      // hand-curated pair data is partial by design — optional fields, honest fallbacks.
      /** @type {{market?: string, retailer?: string, address?: string}} */
      var metro = pair.metro || {};
      /** @type {{market?: string, place?: string, url?: string}} */
      var frontier = pair.frontier || {};
      var card = el('article', 'rx-pair');
      // Metro side: the MARKET leads; the retailer store is subordinate.
      // Never the store name as identity: "Atlanta" then "Publix · address".
      var metroMarket = placeFor(metro.market || pair.market || '');
      card.setAttribute('aria-label', metroMarket + ' paired with ' + (frontier.place || frontier.market || ''));

      var metroSide = el('div', 'rx-pair__side rx-pair__side--metro');
      metroSide.appendChild(el('p', 'rx-pair__kicker', 'metro'));
      metroSide.appendChild(el('h3', 'rx-pair__place', metroMarket));
      var metroMeta = [];
      if (metro.retailer) metroMeta.push(metro.retailer);
      // Unconfirmed store addresses stay tracking-only in the source data —
      // the "confirm —" marker never renders as user-facing copy.
      if (metro.address && !/^confirm\s+—/.test(metro.address)) metroMeta.push(metro.address);
      if (metroMeta.length) metroSide.appendChild(el('p', 'rx-pair__meta', metroMeta.join(' · ')));
      if (pair.retailers && pair.retailers.length) {
        var chips = el('p', 'rx-pair__chips');
        pair.retailers.forEach(function (r) { chips.appendChild(el('span', 'rx-chip', r)); });
        metroSide.appendChild(chips);
      }
      card.appendChild(metroSide);

      card.appendChild(el('div', 'rx-pair__arrow', '→'));

      // Frontier side: farm-stand + monthly produce references.
      var frSide = el('div', 'rx-pair__side rx-pair__side--frontier');
      frSide.appendChild(el('p', 'rx-pair__kicker', 'frontier'));
      frSide.appendChild(el('h3', 'rx-pair__place', frontier.place || frontier.market || pair.market));
      if (frontier.market) frSide.appendChild(el('p', 'rx-pair__meta', frontier.market));
      if (frontier.url) {
        var link = el('a', 'rx-pair__market-link', 'farmers market');
        link.setAttribute('href', frontier.url);
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener');
        frSide.appendChild(link);
      } else {
        frSide.appendChild(el('p', 'rx-pair__meta', 'no confirmed market URL yet'));
      }
      /** @type {Object<string, string>} */
      var monthly = pair.monthly || {};
      var list = el('ul', 'rx-produce');
      MONTHS.forEach(function (mo) {
        var li = el('li', 'rx-produce__item');
        li.appendChild(el('span', 'rx-produce__month', mo.short));
        li.appendChild(el('span', 'rx-produce__ing', orDash(monthly[mo.key])));
        list.appendChild(li);
      });
      frSide.appendChild(list);
      (pair.moments || []).forEach(function (mmt) {
        if (!mmt || !mmt.moment) return;
        var line = el('p', 'rx-pair__moment', mmt.moment + (mmt.status && mmt.status !== 'confirmed' ? ' (proposed)' : ''));
        frSide.appendChild(line);
      });
      card.appendChild(frSide);

      mount.appendChild(card);
    });
    var count = document.getElementById('rxPairsCount');
    if (count) count.textContent = pairs.length + ' metro → frontier pairs';
  }

  // ---- section 3: ingredient -> recipe sample cards (same .rc-card structure) ----
  /**
   * @returns {MonthCard[]}
   */
  function pickSampleCards() {
    var data = window.KODIAK_RECIPE_CARDS;
    if (!data || typeof data !== 'object') return [];
    // const keeps the guard above narrowed inside the forEach closures below.
    const book = data;
    // Deterministic sweep: two sample cards per season with real titles and
    // steps, distinct ingredients, spread across markets.
    var seasons = ['spring', 'summer', 'fall', 'winter'];
    /** @type {Object<string, MonthCard[]>} */
    var bySeason = { spring: [], summer: [], fall: [], winter: [] };
    Object.keys(data).sort().forEach(function (market) {
      MONTHS.forEach(function (mo) {
        var card = (book[market] || {})[mo.key];
        if (card && card.ingredient && card.title && Array.isArray(card.steps) && card.steps.length) {
          bySeason[mo.season].push(card);
        }
      });
    });
    /** @type {Object<string, boolean>} */
    var seenIng = {};
    /** @type {Object<string, boolean>} */
    var usedMarket = {};
    /** @type {Object<string, number>} */
    var have = { spring: 0, summer: 0, fall: 0, winter: 0 };
    /** @type {MonthCard[]} */
    var picks = [];
    // Two passes per season: first spread across markets, then fill gaps.
    // Shared card objects are never mutated — season comes from the month key.
    [false, true].forEach(function (allowRepeatMarket) {
      seasons.forEach(function (season) {
        var list = bySeason[season];
        for (var i = 0; i < list.length && have[season] < 2; i++) {
          var card = list[i];
          var key = String(card.ingredient).toLowerCase();
          if (seenIng[key]) continue;
          var mkt = card.market || '';
          if (!allowRepeatMarket && usedMarket[mkt]) continue;
          seenIng[key] = true;
          usedMarket[mkt] = true;
          picks.push(card);
          have[season]++;
        }
      });
    });
    return picks;
  }

  /**
   * @param {MonthCard} card
   * @returns {HTMLElement}
   */
  function buildSampleCard(card) {
    var rc = el('div', 'rc-card');
    rc.setAttribute('data-substrate', card.substrate || 'kraft');
    rc.setAttribute('role', 'img');
    rc.setAttribute('aria-label', 'Recipe card: ' + (card.title || 'recipe') + ' (' + (card.market || '') + ' ' + (card.month || '') + ')');

    var header = el('header', 'rc-header');
    header.appendChild(makeCorner('left'));
    header.appendChild(el('h3', 'rc-title', card.title || (card.recipe && card.recipe.name) || 'recipe'));
    header.appendChild(makeCorner('right'));
    rc.appendChild(header);

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

    var cols = el('div', 'rc-columns');
    var left = el('section', 'recipe-card-column recipe-card-ingredients');
    left.appendChild(el('h4', 'rc-col-heading', 'ingredients'));
    var ul = el('ul', 'rc-ingredients');
    (card.ingredients || []).forEach(function (ing) {
      var li = el('li', 'rc-ing');
      li.appendChild(el('span', 'rc-ing__name', (ing && ing.qty_name) ? String(ing.qty_name) : ''));
      var priceText = (ing && ing.price != null && String(ing.price).trim().length) ? String(ing.price) : EM_DASH;
      li.appendChild(el('span', 'rc-ing__price', priceText));
      ul.appendChild(li);
    });
    left.appendChild(ul);
    // missing art is an empty RecipeArt — all three zones optional, so the cast is total.
    var art = card.art || /** @type {RecipeArt} */ ({});
    left.appendChild(makeArtZone(ART_ZONES[0], art.raw_ingredient || null));
    cols.appendChild(left);

    var right = el('section', 'recipe-card-column recipe-card-execution');
    right.appendChild(el('h4', 'rc-col-heading', 'steps'));
    var ol = el('ol', 'rc-steps');
    (card.steps || []).forEach(function (step) { ol.appendChild(makeStepLi(step)); });
    // prep drawing above the steps, finished drawing below them: the right
    // column reads top-to-bottom as make-then-plate.
    right.appendChild(makeArtZone(ART_ZONES[1], art.technique || null));
    right.appendChild(ol);
    right.appendChild(makeArtZone(ART_ZONES[2], art.finished_plate || null));
    cols.appendChild(right);
    rc.appendChild(cols);
    return rc;
  }

  /**
   * @param {string|undefined} key
   * @returns {MonthEntry|null}
   */
  function monthName(key) {
    for (var i = 0; i < MONTHS.length; i++) {
      if (MONTHS[i].key === key) return MONTHS[i];
    }
    return null;
  }

  function buildSamples() {
    const mount = document.getElementById('rxSamples');
    if (!mount) return;
    mount.innerHTML = '';
    var picks = pickSampleCards();
    if (!picks.length) {
      mount.appendChild(el('p', 'rc-gallery-empty', 'Sample cards will appear once card data loads.'));
      return;
    }
    var grid = el('div', 'rc-gallery-grid');
    picks.forEach(function (card) {
      var cell = el('div', 'rc-gallery-cell');
      var mo = monthName(card.month);
      cell.appendChild(el('div', 'rc-gallery-month',
        (card.ingredient || '') + ' · ' + (mo ? mo.name + ' (' + mo.season + ')' : (card.month || ''))));
      var shell = el('div', 'rc-card-shell');
      shell.appendChild(buildSampleCard(card));
      cell.appendChild(shell);
      grid.appendChild(cell);
    });
    mount.appendChild(grid);
  }

  function render() {
    buildMatrix();
    bindMatrixFilter();
    buildPairs();
    buildSamples();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }

  window.KODIAK_renderRecipesBrainstorm = render;
})();
