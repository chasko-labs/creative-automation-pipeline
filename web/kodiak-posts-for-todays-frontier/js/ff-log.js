// === ff-log — structured client event log for console debugging ===
// One line per meaningful action, mirrored to the console AND kept in a
// ring buffer at window.__FF_LOG__ (cap 300). window.ffLogExport() downloads
// the buffer as JSON so a session can be shared instead of copy-pasted.
// Everything here is local-only: entries may carry brief text (user data)
// but never secrets — there are none on this page. No deps, classic script,
// must load before the feature scripts it instruments.
(function(){
  'use strict';
  var CAP = 300;
  var buf = [];
  try {
    if (window.__FF_LOG__ && window.__FF_LOG__.length) buf = window.__FF_LOG__;
  } catch (e) {}
  function stamp() {
    try { return new Date().toISOString(); } catch (e) { return ''; }
  }
  function emit(type, data) {
    var entry = { t: stamp(), type: String(type || 'event') };
    try {
      if (data && typeof data === 'object') {
        for (var k in data) {
          if (!Object.prototype.hasOwnProperty.call(data, k)) continue;
          var v = data[k];
          entry[k] = (typeof v === 'string' && v.length > 500) ? v.slice(0, 500) : v;
        }
      }
    } catch (e) {}
    buf.push(entry);
    if (buf.length > CAP) buf.splice(0, buf.length - CAP);
    try {
      var line = '[ff] ' + entry.type;
      var rest = {};
      for (var k2 in entry) {
        if (k2 !== 't' && k2 !== 'type' && Object.prototype.hasOwnProperty.call(entry, k2)) rest[k2] = entry[k2];
      }
      if (entry.type === 'error' || entry.type === 'backend-error') {
        (console.warn || console.log).call(console, line, rest);
      } else {
        (console.log || function(){}).call(console, line, rest);
      }
    } catch (e) {}
    return entry;
  }
  function exportLog() {
    try {
      var blob = new Blob([JSON.stringify(buf, null, 1)], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'ff-log.json';
      document.body.appendChild(a);
      a.click();
      setTimeout(function(){ try { URL.revokeObjectURL(a.href); a.remove(); } catch (e) {} }, 500);
      return true;
    } catch (e) { return false; }
  }
  try {
    window.__FF_LOG__ = buf;
    window.ffLog = emit;
    window.ffLogExport = exportLog;
    window.addEventListener('error', function(ev){
      try { emit('error', { message: String(ev.message || '').slice(0, 300), file: String(ev.filename || '').slice(-80) }); } catch (e) {}
    });
    window.addEventListener('unhandledrejection', function(ev){
      try { var r = ev.reason; emit('error', { message: String((r && r.message) || r || '').slice(0, 300) }); } catch (e) {}
    });
    emit('boot', { url: String(location.href).slice(0, 200) });
  } catch (e) {}
})();
