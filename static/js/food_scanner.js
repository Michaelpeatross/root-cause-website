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
  var lastAt = 0;
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
      return res.json().catch(function () { return { ok: false, error: 'Server did not return a score.' }; });
    });
  }
  function scoreBarcode(code) {
    var digits = String(code || '').replace(/\D+/g, '');
    if (digits.length < 8) return;
    var now = Date.now();
    if (digits === lastCode && now - lastAt < 4000) return;
    lastCode = digits;
    lastAt = now;
    if (camStatus) camStatus.textContent = 'Read ' + digits + ' — scoring…';
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><p>Scoring ' + escapeHtml(digits) + '…</p></div>';
    postJSON('/api/food-scan/barcode', { barcode: digits }).then(renderResult).catch(function () { showError('Network error scoring that barcode.'); });
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
      postJSON('/api/food-scan/photo', { image_b64: parts[1] || '', mime: (parts[0].match(/data:(.*?);/) || [])[1] || 'image/jpeg' }).then(renderResult);
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
      box.innerHTML = items.length ? items.map(function (item) {
        return '<div class="search-hit" data-code="' + escapeHtml(item.code) + '"><strong>' + escapeHtml(item.name) + '</strong></div>';
      }).join('') : '<p>No matches.</p>';
      box.querySelectorAll('.search-hit').forEach(function (rowEl) {
        rowEl.addEventListener('click', function () { scoreBarcode(rowEl.getAttribute('data-code')); });
      });
    });
  });
  function stopCam() {
    if (html5Scanner) {
      html5Scanner.stop().then(function () { html5Scanner.clear(); html5Scanner = null; }).catch(function () { html5Scanner = null; });
    }
    if (camStatus) camStatus.textContent = 'Camera off.';
  }
  function cameraConfig() {
    return {
      fps: 20,
      disableFlip: false,
      qrbox: function (w, h) {
        return { width: Math.max(220, Math.floor(w * 0.94)), height: Math.max(140, Math.floor(h * 0.42)) };
      },
      experimentalFeatures: { useBarCodeDetectorIfSupported: true }
    };
  }
  document.getElementById('start-cam').addEventListener('click', function () {
    if (typeof Html5Qrcode === 'undefined') {
      if (camStatus) camStatus.textContent = 'Decoder did not load. Pull to refresh and try again.';
      return;
    }
    if (html5Scanner) return;
    html5Scanner = new Html5Qrcode('reader', { verbose: false });
    html5Scanner.start({ facingMode: 'environment' }, cameraConfig(), function (decodedText) {
      scoreBarcode(decodedText);
    }).then(function () {
      if (camStatus) camStatus.textContent = 'Live. Fill the box with the barcode — it should score as soon as it locks.';
    }).catch(function (err) {
      if (camStatus) camStatus.textContent = 'Could not start camera (' + (err && err.message ? err.message : 'blocked') + '). Allow camera access.';
    });
  });
  document.getElementById('stop-cam').addEventListener('click', stopCam);
})();
