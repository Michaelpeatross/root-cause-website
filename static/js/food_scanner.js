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
  var lastCode = ''; var lastAt = 0; var running = false;
  function escapeHtml(text) {
    return String(text || '').replace(/&/g,'&').replace(/</g,'<').replace(/>/g,'>');
  }
  function showError(msg) {
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><p>' + escapeHtml(msg) + '</p></div>';
  }
  function postJSON(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (res) { return res.json().catch(function () { return { ok: false, error: 'No score returned.' }; }); });
  }
  function renderResult(data) {
    if (!data || !data.ok) { showError((data && data.error) || 'Could not score that item.'); return; }
    var p = data.product || {}; var r = data.rating || {}; var m = data.macros || {};
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><div class="score-ring" style="background:' + escapeHtml(r.color || '#555') + '"><div class="num">' + escapeHtml(r.score) + '</div><div class="lbl">' + escapeHtml(r.label || '') + '</div></div><h2>' + escapeHtml(p.name || 'Food') + '</h2><p>' + escapeHtml(p.brands || '') + (p.code ? ' · ' + escapeHtml(p.code) : '') + '</p>' + (m.calories ? ('<p>' + escapeHtml(m.calories) + ' kcal · P ' + escapeHtml(m.protein) + ' · C ' + escapeHtml(m.carbs) + ' · F ' + escapeHtml(m.fat) + '</p>') : '') + '<p>Fit for your scan: ' + escapeHtml(r.personal_score) + '/100</p>' + ((r.personal_notes || []).map(function (n) { return '<p>' + escapeHtml(n) + '</p>'; }).join('')) + '</div>';
    loadHistory(); loadDiary();
  }
  function scoreBarcode(code) {
    var digits = String(code || '').replace(/\D+/g, '');
    if (digits.length < 8) return;
    var now = Date.now();
    if (digits === lastCode && now - lastAt < 2500) return;
    lastCode = digits; lastAt = now;
    if (camStatus) camStatus.textContent = 'Read ' + digits + ' — scoring…';
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><p>Scoring ' + escapeHtml(digits) + '…</p></div>';
    postJSON('/api/food-scan/barcode', { barcode: digits }).then(renderResult);
  }
  function loadHistory() {
    var box = document.getElementById('history-list'); if (!box) return;
    fetch('/api/food-scan/history?sort=date_desc').then(function (r) { return r.json(); }).then(function (data) {
      box.innerHTML = ((data && data.items) || []).map(function (item) {
        return '<p><strong>' + escapeHtml(item.name) + '</strong> · ' + escapeHtml(item.score) + '</p>';
      }).join('') || '<p>No scans yet.</p>';
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
      if (box) box.innerHTML = '<p>' + (today.meals || 0) + ' meals · ' + (today.calories || 0) + ' kcal · score ' + (today.avg_score != null ? today.avg_score : '—') + '</p>';
      var days = document.getElementById('diary-days');
      if (days) days.innerHTML = ((data && data.days) || []).map(function (d) {
        return '<p>' + escapeHtml(d.day) + ' · ' + d.calories + ' kcal · score ' + (d.avg_score != null ? d.avg_score : '—') + '</p>';
      }).join('') || '<p>No meals logged yet.</p>';
    }).catch(function () {});
  }
  var typeForm = document.getElementById('type-form');
  if (typeForm) typeForm.addEventListener('submit', function (evt) {
    evt.preventDefault(); scoreBarcode(document.getElementById('barcode').value);
  });
  function decodeFromFile(file) {
    if (!file || typeof Quagga === 'undefined') { showError('Scanner library not ready. Refresh.'); return; }
    var url = URL.createObjectURL(file);
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card"><p>Reading barcode from photo…</p></div>';
    Quagga.decodeSingle({
      src: url,
      numOfWorkers: 0,
      inputStream: { size: 1600 },
      decoder: { readers: ['upc_reader', 'upc_e_reader', 'ean_reader', 'ean_8_reader', 'code_128_reader'] },
      locate: true
    }, function (result) {
      if (result && result.codeResult && result.codeResult.code) {
        scoreBarcode(result.codeResult.code);
      } else {
        showError('Could not read bars in that photo. Get 6 inches away, fill the frame with only the barcode, no glare.');
      }
    });
  }
  var snapBtn = document.getElementById('decode-barcode-photo');
  var snapInput = document.getElementById('barcode-photo');
  if (snapBtn && snapInput) snapBtn.addEventListener('click', function () {
    var file = snapInput.files && snapInput.files[0];
    if (!file) { showError('Take a close photo of the barcode first.'); return; }
    decodeFromFile(file);
  });
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
      var reader = new FileReader();
      reader.onload = function () {
        postJSON(url, { image_b64: String(reader.result || '').split(',')[1] || '', mime: 'image/jpeg' }).then(renderResult);
      };
      reader.readAsDataURL(file);
    });
  }
  bindPhoto('photo', 'preview', 'score-photo', '/api/food-scan/photo');
  bindPhoto('plate', 'plate-preview', 'score-plate', '/api/food-scan/meal');
  function onDetected(result) {
    if (result && result.codeResult && result.codeResult.code) scoreBarcode(result.codeResult.code);
  }
  var startCam = document.getElementById('start-cam');
  if (startCam) startCam.addEventListener('click', function () {
    if (typeof Quagga === 'undefined' || running) return;
    running = true;
    Quagga.init({
      inputStream: { type: 'LiveStream', target: document.getElementById('reader'), constraints: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } } },
      locator: { patchSize: 'large', halfSample: false },
      numOfWorkers: 0,
      frequency: 15,
      decoder: { readers: ['upc_reader', 'upc_e_reader', 'ean_reader', 'ean_8_reader'] },
      locate: true
    }, function (err) {
      if (err) { running = false; if (camStatus) camStatus.textContent = 'Camera failed'; return; }
      Quagga.start();
      if (camStatus) camStatus.textContent = 'Hold 4–6 inches from the bars. Fill the box.';
    });
    Quagga.offDetected(onDetected); Quagga.onDetected(onDetected);
  });
  var stopCam = document.getElementById('stop-cam');
  if (stopCam) stopCam.addEventListener('click', function () { running = false; try { Quagga.stop(); } catch (e) {} });
  loadHistory(); loadGuides(); loadDiary();
})();
