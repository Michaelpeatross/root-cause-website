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
  var video = document.getElementById('video');
  var stream = null;
  var scanning = false;
  var lastCode = '';
  function escapeHtml(text) {
    return String(text || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (res) { return res.json(); });
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
      var b64 = parts[1] || '';
      var mime = (parts[0].match(/data:(.*?);/) || [])[1] || file.type || 'image/jpeg';
      postJSON('/api/food-scan/photo', { image_b64: b64, mime: mime }).then(renderResult).catch(function () { showError('Could not read that photo.'); });
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
      if (!items.length) { box.innerHTML = '<p>No matches. Try the barcode or a label photo.</p>'; return; }
      box.innerHTML = items.map(function (item) {
        return '<div class="search-hit" data-code="' + escapeHtml(item.code) + '"><div><strong>' + escapeHtml(item.name) + '</strong><div style="color:var(--text-muted);font-size:.85rem;">' + escapeHtml(item.brands || item.code) + '</div></div></div>';
      }).join('');
      box.querySelectorAll('.search-hit').forEach(function (rowEl) {
        rowEl.addEventListener('click', function () { scoreBarcode(rowEl.getAttribute('data-code')); });
      });
    }).catch(function () { box.innerHTML = '<p>Search failed. Try a barcode.</p>'; });
  });
  function stopCam() {
    scanning = false;
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    if (camStatus) camStatus.textContent = 'Camera off.';
  }
  function detectLoop() {
    if (!scanning || !video) return;
    if ('BarcodeDetector' in window) {
      var detector = new window.BarcodeDetector({ formats: ['ean_13','ean_8','upc_a','upc_e','code_128'] });
      detector.detect(video).then(function (codes) {
        if (codes && codes[0] && codes[0].rawValue && codes[0].rawValue !== lastCode) {
          lastCode = codes[0].rawValue;
          if (camStatus) camStatus.textContent = 'Found ' + lastCode;
          scoreBarcode(lastCode);
        }
      }).catch(function () {});
    }
    if (scanning) setTimeout(detectLoop, 700);
  }
  document.getElementById('start-cam').addEventListener('click', function () {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (camStatus) camStatus.textContent = 'This browser cannot open the camera. Type the barcode or use a photo.';
      return;
    }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false }).then(function (media) {
      stream = media;
      video.srcObject = media;
      video.play();
      scanning = true;
      if (camStatus) camStatus.textContent = ('BarcodeDetector' in window) ? 'Point at the barcode…' : 'Live barcode reading is limited here. Use Type barcode or a photo.';
      detectLoop();
    }).catch(function () {
      if (camStatus) camStatus.textContent = 'Camera permission denied. Type the barcode or upload a photo.';
    });
  });
  document.getElementById('stop-cam').addEventListener('click', stopCam);
})();
