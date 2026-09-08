(function () {
  'use strict';
  var tabs = document.querySelectorAll('.scan-tabs button');
  tabs.forEach(function (btn) {
    btn.addEventListener('click', function () {
      tabs.forEach(function (b) { b.classList.remove('active'); });
      document.querySelectorAll('.scan-panel').forEach(function (p) { p.classList.remove('active'); });
      btn.classList.add('active');
      var panel = document.getElementById('tab-' + btn.getAttribute('data-tab'));
      if (panel) panel.classList.add('active');
    });
  });
  var resultEl = document.getElementById('result');
  var camStatus = document.getElementById('cam-status');
  var lastCode = '';
  var html5Scanner = null;
  function escapeHtml(text) {
    return String(text || '').replace(/&/g,'&').replace(/</g,'<').replace(/>/g,'>').replace(/"/g,'"');
  }
  function showError(msg) {
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><p>' + escapeHtml(msg) + '</p></div>';
  }
  function row(label, value) {
    return '<div class="break-row"><span>' + escapeHtml(label) + '</span><strong>' + escapeHtml(value) + '/100</strong></div>';
  }
  function renderResult(data) {
    if (!data || !data.ok) { showError((data && data.error) || 'Could not score that item.'); return; }
    var p = data.product || {};
    var r = data.rating || {};
    var notes = (r.personal_notes || []).map(function (n) { return '<p class="hit">' + escapeHtml(n) + '</p>'; }).join('');
    var additives = (r.additive_hits || []).length ? '<p class="hit">Caution additives: ' + escapeHtml(r.additive_hits.join(', ')) + '</p>' : '';
    var img = p.image ? '<img class="prod" src="' + escapeHtml(p.image) + '" alt="">' : '';
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><div class="score-ring" style="background:' + escapeHtml(r.color || '#555') + '"><div class="num">' + escapeHtml(r.score) + '</div><div class="lbl">' + escapeHtml(r.label || '') + '</div></div><div style="display:flex;gap:1rem;">' + img + '<div><h2 style="margin:0 0 .25rem;">' + escapeHtml(p.name || 'Product') + '</h2><p style="color:var(--text-muted);margin:0;">' + escapeHtml(p.brands || '') + (p.code ? ' · ' + escapeHtml(p.code) : '') + '</p></div></div><div style="margin-top:1rem;">' + row('Nutrition quality', r.nutrition_score) + row('Additives / processing', r.additive_score) + row('Fit for your scan', r.personal_score) + '</div>' + notes + additives + (p.ingredients ? '<p style="font-size:.85rem;margin-top:1rem;"><strong>Ingredients</strong><br>' + escapeHtml(p.ingredients).slice(0, 600) + '</p>' : '') + '</div>';
    resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function postJSON(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (res) {
      return res.json().catch(function () { return { ok: false, error: 'Server did not return a score. Try Type barcode.' }; });
    });
  }
  function scoreBarcode(code) {
    if (!code) return;
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><p>Scoring ' + escapeHtml(code) + '…</p></div>';
    postJSON('/api/food-scan/barcode', { barcode: code }).then(renderResult).catch(function () { showError('Network error scoring that barcode.'); });
  }
  document.getElementById('type-form').addEventListener('submit', function (evt) {
    evt.preventDefault();
    scoreBarcode(document.getElementById('barcode').value.trim());
  });
  var photoInput = document.getElementById('photo');
  var preview = document.getElementById('preview');
  photoInput.addEventListener('change', function () {
    var file = photoInput.files && photoInput.files[0];
    if (!file) return;
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
  });
  document.getElementById('score-photo').addEventListener('click', function () {
    var file = photoInput.files && photoInput.files[0];
    if (!file) { showError('Choose a label photo first.'); return; }
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><p>Reading the label…</p></div>';
    var reader = new FileReader();
    reader.onload = function () {
      var raw = String(reader.result || '');
      var parts = raw.split(',');
      postJSON('/api/food-scan/photo', { image_b64: parts[1] || '', mime: (parts[0].match(/data:(.*?);/) || [])[1] || file.type || 'image/jpeg' }).then(renderResult).catch(function () { showError('Could not read that photo.'); });
    };
    reader.readAsDataURL(file);
  });
  document.getElementById('search-form').addEventListener('submit', function (evt) {
    evt.preventDefault();
    var q = document.getElementById('q').value.trim();
    var box = document.getElementById('search-results');
    box.innerHTML = '<p>Searching…</p>';
    postJSON('/api/food-scan/search', { q: q }).then(function (data) {
      var items = (data && data.results) || [];
      if (!items.length) { box.innerHTML = '<p>No matches. Try Type barcode.</p>'; return; }
      box.innerHTML = items.map(function (item) {
        return '<div class="search-hit" data-code="' + escapeHtml(item.code) + '"><div><strong>' + escapeHtml(item.name) + '</strong><div style="color:var(--text-muted);font-size:.85rem;">' + escapeHtml(item.brands || item.code) + '</div></div></div>';
      }).join('');
      box.querySelectorAll('.search-hit').forEach(function (rowEl) {
        rowEl.addEventListener('click', function () { scoreBarcode(rowEl.getAttribute('data-code')); });
      });
    }).catch(function () { box.innerHTML = '<p>Search failed. Try a barcode.</p>'; });
  });
  function stopCam() {
    if (html5Scanner) {
      html5Scanner.stop().then(function () { html5Scanner.clear(); html5Scanner = null; }).catch(function () { html5Scanner = null; });
    }
    if (camStatus) camStatus.textContent = 'Camera off.';
  }
  document.getElementById('start-cam').addEventListener('click', function () {
    if (typeof Html5Qrcode === 'undefined') {
      if (camStatus) camStatus.textContent = 'Decoder missing. Type the numbers under the bars.';
      return;
    }
    if (html5Scanner) return;
    var formats = [];
    if (window.Html5QrcodeSupportedFormats) {
      var F = window.Html5QrcodeSupportedFormats;
      formats = [F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E, F.CODE_128, F.CODE_39].filter(function (x) { return x != null; });
    }
    var config = { fps: 12, qrbox: { width: 280, height: 160 }, aspectRatio: 1.777 };
    if (formats.length) config.formatsToSupport = formats;
    html5Scanner = new Html5Qrcode('reader');
    html5Scanner.start({ facingMode: 'environment' }, config, function (decoded) {
      var digits = String(decoded || '').replace(/\D+/g, '');
      if (digits.length < 8 || digits === lastCode) return;
      lastCode = digits;
      if (camStatus) camStatus.textContent = 'Found ' + digits;
      scoreBarcode(digits);
    }).then(function () {
      if (camStatus) camStatus.textContent = 'Hold the barcode flat inside the box. Wrinkled bags are hard — type the numbers if it sits there.';
    }).catch(function () {
      if (camStatus) camStatus.textContent = 'Camera permission denied. Type the numbers under the bars.';
    });
  });
  document.getElementById('stop-cam').addEventListener('click', stopCam);
})();
