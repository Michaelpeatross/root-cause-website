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
    if (!resultEl) return;
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><p>' + escapeHtml(msg) + '</p></div>';
  }
  function row(label, value) {
    return '<div class="break-row"><span>' + escapeHtml(label) + '</span><strong>' + escapeHtml(value) + '/100</strong></div>';
  }
  function loadHistory() {
    var box = document.getElementById('history-list');
    var sortEl = document.getElementById('hist-sort');
    if (!box) return;
    var sort = sortEl ? sortEl.value : 'date_desc';
    fetch('/api/food-scan/history?sort=' + encodeURIComponent(sort)).then(function (r) { return r.json(); }).then(function (data) {
      var items = (data && data.items) || [];
      if (!items.length) { box.innerHTML = '<p>No scans saved yet. Scan a barcode and it will show up here.</p>'; return; }
      box.innerHTML = items.map(function (item) {
        var img = item.image ? '<img src="' + escapeHtml(item.image) + '" alt="">' : '<div></div>';
        return '<div class="hist-row">' + img + '<div><strong>' + escapeHtml(item.name || '') + '</strong><div style="color:#667;font-size:.85rem;">' + escapeHtml(item.brands || '') + '<br>' + escapeHtml(item.scanned_at || '') + '</div></div><strong>' + escapeHtml(item.score) + '</strong></div>';
      }).join('');
    }).catch(function () { box.innerHTML = '<p>Could not load history.</p>'; });
  }
  function loadGuides() {
    fetch('/api/food-scan/guides').then(function (r) { return r.json(); }).then(function (data) {
      var top = document.getElementById('top-foods');
      var low = document.getElementById('low-foods');
      if (top) top.innerHTML = ((data && data.top) || []).map(function (x) { return '<li>' + escapeHtml(x) + '</li>'; }).join('');
      if (low) low.innerHTML = ((data && data.low) || []).map(function (x) { return '<li>' + escapeHtml(x) + '</li>'; }).join('');
    }).catch(function () {});
  }
  function renderResult(data) {
    if (!data || !data.ok) { showError((data && data.error) || 'Could not score that item.'); return; }
    var p = data.product || {};
    var r = data.rating || {};
    var notes = (r.personal_notes || []).map(function (n) { return '<p class="hit">' + escapeHtml(n) + '</p>'; }).join('');
    var img = p.image ? '<img class="prod" src="' + escapeHtml(p.image) + '" alt="">' : '';
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><div class="score-ring" style="background:' + escapeHtml(r.color || '#555') + '"><div class="num">' + escapeHtml(r.score) + '</div><div class="lbl">' + escapeHtml(r.label || '') + '</div></div><div style="display:flex;gap:1rem;">' + img + '<div><h2 style="margin:0 0 .25rem;">' + escapeHtml(p.name || 'Product') + '</h2><p style="color:var(--text-muted);margin:0;">' + escapeHtml(p.brands || '') + (p.code ? ' · ' + escapeHtml(p.code) : '') + '</p></div></div><div style="margin-top:1rem;">' + row('Nutrition quality', r.nutrition_score) + row('Additives / processing', r.additive_score) + row('Fit for your scan', r.personal_score) + '</div>' + notes + '</div>';
    loadHistory();
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
    postJSON('/api/food-scan/barcode', { barcode: digits }).then(renderResult);
  }
  document.getElementById('type-form').addEventListener('submit', function (evt) {
    evt.preventDefault();
    scoreBarcode(document.getElementById('barcode').value.trim());
  });
  var photoInput = document.getElementById('photo');
  var preview = document.getElementById('preview');
  if (photoInput) photoInput.addEventListener('change', function () {
    var file = photoInput.files && photoInput.files[0];
    if (!file || !preview) return;
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
  });
  var scorePhoto = document.getElementById('score-photo');
  if (scorePhoto) scorePhoto.addEventListener('click', function () {
    var file = photoInput && photoInput.files && photoInput.files[0];
    if (!file) { showError('Choose a label photo first.'); return; }
    var reader = new FileReader();
    reader.onload = function () {
      var parts = String(reader.result || '').split(',');
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
    scoreBarcode(result.codeResult.code);
  }
  function stopCam() {
    running = false;
    try { if (window.Quagga) Quagga.stop(); } catch (e) {}
    if (camStatus) camStatus.textContent = 'Camera off.';
  }
  document.getElementById('start-cam').addEventListener('click', function () {
    if (typeof Quagga === 'undefined') {
      if (camStatus) camStatus.textContent = 'Scanner library did not load. Refresh the page.';
      return;
    }
    if (running) return;
    running = true;
    Quagga.init({
      inputStream: { name: 'Live', type: 'LiveStream', target: document.getElementById('reader'), constraints: { facingMode: 'environment' } },
      locator: { patchSize: 'medium', halfSample: true },
      numOfWorkers: 0,
      frequency: 12,
      decoder: { readers: ['upc_reader', 'upc_e_reader', 'ean_reader', 'ean_8_reader', 'code_128_reader'] },
      locate: true
    }, function (err) {
      if (err) { running = false; if (camStatus) camStatus.textContent = 'Camera failed: ' + (err.message || err); return; }
      Quagga.start();
      if (camStatus) camStatus.textContent = 'Live grocery scanner.';
    });
    Quagga.offDetected(onDetected);
    Quagga.onDetected(onDetected);
  });
  document.getElementById('stop-cam').addEventListener('click', stopCam);
  var sortEl = document.getElementById('hist-sort');
  if (sortEl) sortEl.addEventListener('change', loadHistory);
  loadHistory();
  loadGuides();
})();
