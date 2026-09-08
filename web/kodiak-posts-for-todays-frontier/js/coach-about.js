// === Coach Q&A in About (Unit 4) — ask how, confirm to apply ===
// Lives inside the collapsed #aboutTool body: ask box + answer + confirm chips.
// /ask returns {answer, edits[]}; each edit renders as a confirm chip and ONLY
// a click dispatches the real DOM action (chip click, brief append + input
// event, market option click). Dark without a coach URL: no box, no fetch.
(function(){
  'use strict';
  function coachUrl(){
    try{
      var m = document.querySelector('meta[name="kodiak-coach-url"]');
      var u = m && m.getAttribute('content');
      return (u && u.trim()) ? u.trim().replace(/\/$/, '') : null;
    }catch(e){ return null; }
  }
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function mount(){
    try{
      if(document.getElementById('coachAsk') || !coachUrl()) return;
      var body = document.querySelector('#aboutTool .body');
      if(!body) return;
      var wrap = document.createElement('div');
      wrap.id = 'coachAsk';
      wrap.innerHTML =
        '<h4>Ask the coach</h4>' +
        '<p class="hint">How do I get a Costco version? Why did Preview stay grey? Answers cite the steps; suggested edits apply only when you confirm.</p>' +
        '<div class="coach-row"><input id="coachQ" type="text" maxlength="500" placeholder="Ask how to get the result you want…" aria-label="Ask the campaign coach">' +
        '<button type="button" class="btn ghost" id="coachGo">Ask</button></div>' +
        '<div id="coachAnswer" role="status" aria-live="polite"></div>' +
        '<div id="coachEdits"></div>';
      body.appendChild(wrap);
      var go = document.getElementById('coachGo');
      var q = document.getElementById('coachQ');
      go.addEventListener('click', ask);
      q.addEventListener('keydown', function(e){ if(e.key === 'Enter') ask(); });
    }catch(e){ /* enhancement only */ }
  }

  function pageState(){
    try{
      var chips = [];
      Array.prototype.forEach.call(
        document.querySelectorAll('#promptChips .ff-chip[aria-pressed="true"]'),
        function(c){ chips.push(c.getAttribute('data-theme')); });
      var brief = document.getElementById('campaignBrief');
      var market = document.getElementById('marketButtonLabel');
      return {
        chips: chips,
        market: market ? market.textContent.trim().slice(0, 120) : '',
        briefLength: brief ? brief.value.length : 0,
      };
    }catch(e){ return {}; }
  }

  function ask(){
    try{
      var url = coachUrl();
      var q = document.getElementById('coachQ');
      var ans = document.getElementById('coachAnswer');
      var box = document.getElementById('coachEdits');
      if(!url || !q || !ans) return;
      var question = q.value.trim();
      if(!question) return;
      ans.textContent = 'Asking the coach…';
      box.innerHTML = '';
      fetch(url + '/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question, pageState: pageState() }),
      }).then(function(r){
        if(!r.ok) throw new Error('http ' + r.status);
        return r.json();
      }).then(function(j){
        ans.textContent = (j && j.answer) || 'No answer.';
        renderEdits(box, (j && j.edits) || []);
      }).catch(function(){
        ans.textContent = 'The coach is busy — try again.';
      });
    }catch(e){ /* never break the page */ }
  }

  function renderEdits(box, edits){
    box.innerHTML = '';
    edits.slice(0, 3).forEach(function(e){
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn ghost coach-confirm';
      b.textContent = 'Apply: ' + (e.label || e.target);
      b.addEventListener('click', function(){ applyEdit(e, box); });
      box.appendChild(b);
    });
  }

  // Every op below reuses the page's own controls — no shadow state, so undo,
  // toggle math, and persistence all behave exactly as manual clicks.
  function applyEdit(e, box){
    try{
      var note = document.createElement('p');
      note.className = 'hint';
      if(e.op === 'toggle-chip'){
        var chip = document.querySelector('#promptChips .ff-chip[data-theme="' + e.target.replace(/"/g, '') + '"]');
        if(chip){ chip.click(); note.textContent = 'Toggled ' + e.target + '.'; }
        else{ note.textContent = 'Could not find that direction (' + e.target + ').'; }
      } else if(e.op === 'append-brief'){
        var brief = document.getElementById('campaignBrief');
        if(brief){
          brief.focus();
          brief.value = (brief.value + ' ' + e.target).trim();
          brief.dispatchEvent(new Event('input', { bubbles: true }));
          note.textContent = 'Added to your brief.';
        } else{ note.textContent = 'Brief box not found.'; }
      } else if(e.op === 'set-market'){
        var found = null;
        Array.prototype.forEach.call(
          document.querySelectorAll('#marketListbox [role="option"], #marketListbox button, #marketListbox li'),
          function(o){ if(!found && o.textContent.trim().toLowerCase().indexOf(String(e.target).toLowerCase()) !== -1) found = o; });
        if(found){ found.click(); note.textContent = 'Market set to ' + e.target + '.'; }
        else{ note.textContent = 'Could not find that market (' + e.target + ').'; }
      } else{
        note.textContent = 'Unknown edit — nothing applied.';
      }
      box.innerHTML = '';
      box.appendChild(note);
    }catch(err){ /* honest no-op */ }
  }

  try{ mount(); }catch(e){}
})();
