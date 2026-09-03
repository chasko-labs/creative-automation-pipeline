/* glimmer-proxy.js — dev-only WebMCP bridge: Generate hits 127.0.0.1:8181 when local, else Nova unlimited
   Loaded via <script src="glimmer-proxy.js"> in index.html. No build, file:// friendly.
   - Local (127.0.0.1:8099 or localhost): POST http://127.0.0.1:8181/v1/chat/completions for brief→JSON, SKU rank, local flavor, diagnose
   - Hosted (d37333 / kodiak.bryanchasko.com / frontier): no localhost → fallback to Nova unlimited (offline dict only if Nova unreachable)
   Exposes window.GlimmerProxy = { chat, parseBrief, pickSkus, diagnose } for index.html + console ping-pong.
   Cost doc: Nova Canvas per-image + Micro per-translate + Translate per-char + CloudFront per-GB (unlimited, go ham on embeddings).
*/
(function(){
  const GLIMMER = (location.hostname === '127.0.0.1' || location.hostname === 'localhost') ? 'http://127.0.0.1:8181/v1' : null;
  const MODEL = 'muse-glimmer-30b';
  async function chat(prompt, max_tokens=256, system){
    if(!GLIMMER) return null; // hosted → use Nova
    const msgs = system ? [{role:'system', content: system}, {role:'user', content: prompt}] : [{role:'user', content: prompt}];
    try{
      const r = await fetch(GLIMMER + '/chat/completions', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({model: MODEL, messages: msgs, max_tokens, temperature: 0.3})});
      if(!r.ok){ console.log('[glimmer-proxy] chat', r.status, await r.text().then(t=>t.slice(0,120))); return null; }
      const j = await r.json(); return j.choices?.[0]?.message?.content?.trim() || null;
    }catch(e){ console.log('[glimmer-proxy] unreachable (dev-only, fallback to Nova):', e.message||e); return null; }
  }
  async function parseBrief(briefText){
    const sys = 'You parse KODIAK frontier campaign briefs into JSON. Return ONLY JSON with keys: campaign_message, suggested_products (up to 3), audience_hint, region_hint';
    const out = await chat('Parse this brief into JSON, no prose:\n'+briefText, 400, sys);
    if(!out) return null; try{ const i=out.indexOf('{'), j=out.lastIndexOf('}'); if(i!==-1&&j!==-1) return JSON.parse(out.slice(i,j+1)); }catch(e){ console.log('[glimmer-proxy] parseBrief json fail', e, out.slice(0,120)); } return null;
  }
  async function pickSkus(briefText, catalogNames, k=3){
    const sys = `You are a KODIAK SKU ranker. Catalog ${catalogNames.length} products. Return ONLY JSON array of ${k} exact names, no prose.`;
    const out = await chat(`Brief: ${briefText}\nCatalog: ${JSON.stringify(catalogNames.slice(0,40))}\nPick ${k}.`, 200, sys);
    if(!out) return null; try{ const m=out.match(/\[.*\]/s); if(m){ const arr=JSON.parse(m[0]); const f=arr.filter(x=>catalogNames.includes(x)).slice(0,k); if(f.length===k) return f; } }catch(e){} return null;
  }
  async function diagnose(htmlSnippet, hint){
    const sys = 'You are a KODIAK brand QA + taste linter. Check: Bear at 24,24, Blaze ≤18% or 8px bar, gin headings (zjt4wyq n4) + museo-sans body, kodiak_sans hosted, Roar utility only, no purple/aura/cream/glass/bento/hover:scale. Return bullet fixes.';
    return await chat(`HTML snippet (800):\n${htmlSnippet.slice(0,800)}\nScreenshot hint: ${hint}\nList violations and fixes, no fluff.`, 500, sys);
  }
  window.GlimmerProxy = { chat, parseBrief, pickSkus, diagnose, isLocal: !!GLIMMER, endpoint: GLIMMER };
  console.log('%c[GlimmerProxy] ' + (GLIMMER ? 'local 8181 enabled — Generate will hit glimmer for brief→SKU/flavor/diagnose, then Nova unlimited' : 'hosted — Generate uses Nova unlimited (glimmer dev-only)'), 'color:#1A3C34;font-weight:700');
  // ping-pong helper: ⌘S → diagnose front page (also used by diagnose.sh)
  window.glimmerDiagnoseFrontPage = async function(){
    const html = document.documentElement.outerHTML.slice(0,2000);
    const res = await diagnose(html, 'header brand red #B51E14/ #382316, brown texture 20pt URB, preview Bear 24,24');
    console.log('%c[Glimmer diagnose]', 'background:#B51E14;color:#FFF8F0;padding:2px 6px;border-radius:6px', res || '(fallback to Nova — glimmer offline, check supervisor at 127.0.0.1:8181)');
    return res;
  };
})();
