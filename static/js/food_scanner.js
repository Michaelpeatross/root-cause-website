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
    if (!box) return;
    var sort = (document.getElementById('hist-sort') || {}).value || 'date_desc';
    fetch('/api/food-scan/history?sort=' + encodeURIComponent(sort)).then(function (r) { return r.json(); }).then(function (data) {
      var items = (data && data.items) || [];
      box.innerHTML = items.length ? items.map(function (item) {
        return '<p><strong>' + escapeHtml(item.name) + '</strong> · ' + escapeHtml(item.scanned_at) + ' · ' + escapeHtml(item.score) + '</p>';
      }).join('') : '<p>No barcode scans yet.</p>';
    }).catch(function () {});
  }
  function loadGuides() {
    fetch('/api/food-scan/guides').then(function (r) { return r.json(); }).then(function (data) {
      var top = document.getElementById('top-foods'); var low = document.getElementById('low-foods');
      if (top) top.innerHTML = ((data && data.top) || []).map(function (x) { return '<li>' + escapeHtml(x) + '</li>'; }).join('');
      if (low) low.innerHTML = ((data && data.low) || []).map(function (x) { return '<li>' + escapeHtml(x) + '</li>'; }).join('');
    }).catch(function () {});
  }
  function loadDiary() {
    fetch('/api/food-scan/diary').then(function (r) { return r.json(); }).then(function (data) {
      var today = (data && data.today) || {};
      var box = document.getElementById('diary-today');
      if (box) {
        box.innerHTML = '<p><strong>' + (today.meals || 0) + ' meals today</strong> · avg score ' + (today.avg_score != null ? today.avg_score : '—') + '</p>'
          + '<div class="macro-grid">'
          + '<div><div>Calories</div><strong>' + (today.calories || 0) + '</strong></div>'
          + '<div><div>Protein</div><strong>' + (today.protein || 0) + ' g</strong></div>'
          + '<div><div>Carbs</div><strong>' + (today.carbs || 0) + ' g</strong></div>'
          + '<div><div>Fat</div><strong>' + (today.fat || 0) + ' g</strong></div>'
          + '<div><div>Sugar</div><strong>' + (today.sugar || 0) + ' g</strong></div>'
          + '</div>';
      }
      var days = document.getElementById('diary-days');
      if (days) {
        days.innerHTML = ((data && data.days) || []).map(function (d) {
          return '<p>' + escapeHtml(d.day) + ' · ' + d.meals + ' meals · ' + d.calories + ' kcal · score ' + (d.avg_score != null ? d.avg_score : '—') + '</p>';
        }).join('') || '<p>No meals logged yet. Use Plate photo.</p>';
      }
    }).catch(function () {});
  }
  function renderResult(data) {
    if (!data || !data.ok) { showError((data && data.error) || 'Could not score that item.'); return; }
    var p = data.product || {}; var r = data.rating || {}; var m = data.macros || {};
    var notes = (r.personal_notes || []).map(function (n) { return '<p class="hit">' + escapeHtml(n) + '</p>'; }).join('');
    var macros = m.calories ? ('<div class="macro-grid"><div>Cal <strong>' + escapeHtml(m.calories) + '</strong></div><div>P <strong>' + escapeHtml(m.protein) + 'g</strong></div><div>C <strong>' + escapeHtml(m.carbs) + 'g</strong></div><div>F <strong>' + escapeHtml(m.fat) + 'g</strong></div><div>Sugar <strong>' + escapeHtml(m.sugar) + 'g</strong></div></div>') : '';
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><div class="score-ring" style="background:' + escapeHtml(r.color || '#555') + '"><div class="num">' + escapeHtml(r.score) + '</div><div class="lbl">' + escapeHtml(r.label || '') + '</div></div><h2>' + escapeHtml(p.name || 'Food') + '</h2>' + macros + row('Nutrition quality', r.nutrition_score) + row('Fit for your scan', r.personal_score) + notes + (m.notes ? '<p>' + escapeHtml(m.notes) + '</p>' : '') + '</div>';
    loadHistory(); loadDiary();
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
    lastCode = digits; lastAt = now;
    postJSON('/api/food-scan/barcode', { barcode: digits }).then(renderResult);
  }
  var typeForm = document.getElementById('type-form');
  if (typeForm) typeForm.addEventListener('submit', function (evt) { evt.preventDefault(); scoreBarcode(document.getElementById('barcode').value.trim()); });
  function bindPhoto(inputId, previewId, buttonId, url) {
    var input = document.getElementById(inputId);
    var preview = document.getElementById(previewId);
    var button = document.getElementById(buttonId);
    if (input && preview) input.addEventListener('change', function () {
      var file = input.files && input.files[0]; if (!file) return; preview.src = URL.createObjectURL(file); preview.hidden = false;
    });
    if (button) button.addEventListener('click', function () {
      var file = input && input.files && input.files[0];
      if (!file) { showError('Choose a photo first.'); return; }
      resultEl.hidden = false; resultEl.innerHTML = '<div class="card"><p>Reading the photo…</p></div>';
      var reader = new FileReader();
      reader.onload = function () {
        var parts = String(reader.result || '').split(',');
        postJSON(url, { image_b64: parts[1] || '', mime: 'image/jpeg' }).then(renderResult);
      };
      reader.readAsDataURL(file);
    });
  }
  bindPhoto('photo', 'preview', 'score-photo', '/api/food-scan/photo');
  bindPhoto('plate', 'plate-preview', 'score-plate', '/api/food-scan/meal');
  var searchForm = document.getElementById('search-form');
  if (searchForm) searchForm.addEventListener('submit', function (evt) {
    evt.preventDefault();
    postJSON('/api/food-scan/search', { q: document.getElementById('q').value.trim() }).then(function (data) {
      var box = document.getElementById('search-results');
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
    if (result && result.codeResult && result.codeResult.code) scoreBarcode(result.codeResult.code);
  }
  var startCam = document.getElementById('start-cam');
  if (startCam) startCam.addEventListener('click', function () {
    if (typeof Quagga === 'undefined' || running) return;
    running = true;
    Quagga.init({ inputStream: { type: 'LiveStream', target: document.getElementById('reader'), constraints: { facingMode: 'environment' } }, numOfWorkers: 0, decoder: { readers: ['upc_reader', 'ean_reader', 'upc_e_reader'] } }, function (err) {
      if (err) { running = false; if (camStatus) camStatus.textContent = 'Camera failed'; return; }
      Quagga.start(); if (camStatus) camStatus.textContent = 'Live grocery scanner.';
    });
    Quagga.offDetected(onDetected); Quagga.onDetected(onDetected);
  });
  var stopCam = document.getElementById('stop-cam');
  if (stopCam) stopCam.addEventListener('click', function () { running = false; try { Quagga.stop(); } catch (e) {} });
  var sortEl = document.getElementById('hist-sort');
  if (sortEl) sortEl.addEventListener('change', loadHistory);
  loadHistory(); loadGuides(); loadDiary();
})();
