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
  var running = false;
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
    if (digits === lastCode && now - lastAt < 3500) return;
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
    var reader = new FileReader();
    reader.onload = function () {
      var raw = String(reader.result || '');
      var parts = raw.split(',');
      postJSON('/api/food-scan/photo', { image_b64: parts[1] || '', mime: 'image/jpeg' }).then(renderResult);
    };
    reader.readAsDataURL(file);
  });
  document.getElementById('search-form').addEventListener('submit', function (evt) {
    evt.preventDefault();
    var box = document.getElementById('search-results');
    box.innerHTML = '<p>Searching…</p>';
    postJSON('/api/food-scan/search', { q: document.getElementById('q').value.trim() }).then(function (data) {
      var items = (data && data.results) || [];
      box.innerHTML = items.length ? items.map(function (item) {
        return '<div class="search-hit" data-code="' + escapeHtml(item.code) + '"><strong>' + escapeHtml(item.name) + '</strong></div>';
      }).join('') : '<p>No matches.</p>';
      box.querySelectorAll('.search-hit').forEach(function (el) {
        el.addEventListener('click', function () { scoreBarcode(el.getAttribute('data-code')); });
      });
    });
  });
  function onDetected(result) {
    if (!result || !result.codeResult || !result.codeResult.code) return;
    var err = result.codeResult.decodedCodes || [];
    var errors = 0;
    err.forEach(function (c) { if (c.error) errors += c.error; });
    if (err.length && errors / err.length > 0.25) return;
    scoreBarcode(result.codeResult.code);
  }
  function stopCam() {
    running = false;
    try { if (window.Quagga) Quagga.stop(); } catch (e) {}
    if (camStatus) camStatus.textContent = 'Camera off.';
  }
  document.getElementById('start-cam').addEventListener('click', function () {
    if (typeof Quagga === 'undefined') {
      if (camStatus) camStatus.textContent = 'Scanner library did not load. Refresh the page on Wi-Fi.';
      return;
    }
    if (running) return;
    running = true;
    if (camStatus) camStatus.textContent = 'Starting camera…';
    Quagga.init({
      inputStream: {
        name: 'Live',
        type: 'LiveStream',
        target: document.getElementById('reader'),
        constraints: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
      },
      locator: { patchSize: 'medium', halfSample: true },
      numOfWorkers: 0,
      frequency: 12,
      decoder: {
        readers: ['upc_reader', 'upc_e_reader', 'ean_reader', 'ean_8_reader', 'code_128_reader']
      },
      locate: true
    }, function (err) {
      if (err) {
        running = false;
        if (camStatus) camStatus.textContent = 'Camera failed: ' + (err.message || err);
        return;
      }
      Quagga.start();
      if (camStatus) camStatus.textContent = 'Live grocery scanner. Hold the barcode steady 6 inches away.';
    });
    Quagga.offDetected(onDetected);
    Quagga.onDetected(onDetected);
  });
  document.getElementById('stop-cam').addEventListener('click', stopCam);
})();
