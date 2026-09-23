(function () {
  'use strict';
  var loggedIn = !!(window.RC_FOOD && window.RC_FOOD.loggedIn);
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
    return String(text == null ? '' : text)
      .replace(/&/g, '&')
      .replace(/</g, '<')
      .replace(/>/g, '>')
      .replace(/"/g, '"');
  }
  function showError(msg) {
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="status-banner err" role="alert">' + escapeHtml(msg) + '</div>';
  }
  function showLoad(msg) {
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="status-banner load">' + escapeHtml(msg) + '</div>';
  }
  function fmt(val, unit) {
    if (val == null || val === '') return '—';
    var n = Number(val);
    if (isNaN(n)) return escapeHtml(val);
    return (Math.round(n * 10) / 10) + (unit ? ' ' + unit : '');
  }
  function postJSON(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (res) { return res.json().catch(function () { return { ok: false, error: 'No result returned.' }; }); });
  }
  function renderResult(data) {
    if (!data || !data.ok) { showError((data && data.error) || 'Could not estimate that item.'); return; }
    var p = data.product || {}; var r = data.rating || {}; var m = data.macros || {};
    var guestNote = data.guest ? '<p class="guest-cta">Create a free account to save this estimate to your nutrition history.</p>' : (data.saved ? '<p class="hint">Saved to your nutrition log.</p>' : '');
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card">' +
      (r.score != null ? '<div class="score-ring" style="background:' + escapeHtml(r.color || '#555') + '"><div class="num">' + escapeHtml(r.score) + '</div><div>' + escapeHtml(r.label || '') + '</div></div>' : '') +
      '<h2>' + escapeHtml(p.name || 'Food') + '</h2>' +
      '<p>' + escapeHtml(p.brands || '') + (p.code ? ' · ' + escapeHtml(p.code) : '') + '</p>' +
      '<div class="macro-grid">' +
        '<div><strong>' + fmt(m.calories) + '</strong><div class="hint">kcal</div></div>' +
        '<div><strong>' + fmt(m.protein, 'g') + '</strong><div class="hint">protein</div></div>' +
        '<div><strong>' + fmt(m.carbs, 'g') + '</strong><div class="hint">carbs</div></div>' +
        '<div><strong>' + fmt(m.fat, 'g') + '</strong><div class="hint">fat</div></div>' +
        '<div><strong>' + fmt(m.fiber, 'g') + '</strong><div class="hint">fiber</div></div>' +
        '<div><strong>' + fmt(m.sugar, 'g') + '</strong><div class="hint">sugar</div></div>' +
        '<div><strong>' + fmt(m.sodium) + '</strong><div class="hint">sodium</div></div>' +
      '</div>' +
      '<p class="hint" style="margin-top:1rem;"><strong>' + escapeHtml(data.confidence || 'estimate') + '</strong> — ' + escapeHtml(data.uncertainty || 'Educational estimate only. Not medical advice.') + '</p>' +
      (m.notes ? '<p>' + escapeHtml(m.notes) + '</p>' : '') +
      ((r.personal_notes || []).map(function (n) { return '<p>' + escapeHtml(n) + '</p>'; }).join('')) +
      guestNote + '</div>';
    if (loggedIn) { loadHistory(); loadDiary(); }
  }
  function scoreBarcode(code) {
    var digits = String(code || '').replace(/\D+/g, '');
    if (digits.length < 8) { showError('Enter at least 8 barcode digits.'); return; }
    var now = Date.now();
    if (digits === lastCode && now - lastAt < 2500) return;
    lastCode = digits; lastAt = now;
    if (camStatus) camStatus.textContent = 'Read ' + digits + ' — looking up…';
    showLoad('Looking up ' + digits + '…');
    postJSON('/api/food-scan/barcode', { barcode: digits }).then(renderResult);
  }
  function loadHistory() {
    var box = document.getElementById('history-list'); if (!box) return;
    fetch('/api/food-scan/history').then(function (r) { return r.json(); }).then(function (data) {
      var items = (data && data.items) || [];
      box.innerHTML = items.length ? items.map(function (item) {
        return '<p><strong>' + escapeHtml(item.name) + '</strong> · ' + escapeHtml(item.score) + ' · ' + escapeHtml(item.scanned_at || '') + '</p>';
      }).join('') : '<p class="hint">No scans saved yet.</p>';
    }).catch(function () { box.textContent = 'Could not load history.'; });
  }
  function loadDiary() {
    var todayBox = document.getElementById('diary-today');
    var daysBox = document.getElementById('diary-days');
    if (!todayBox && !daysBox) return;
    fetch('/api/food-scan/diary').then(function (r) { return r.json(); }).then(function (data) {
      var today = (data && data.today) || {};
      if (todayBox) todayBox.innerHTML = '<p>' + (today.meals || 0) + ' meals · ' + (today.calories || 0) + ' kcal</p>';
      if (daysBox) daysBox.innerHTML = ((data.days || []).map(function (d) {
        return '<p>' + escapeHtml(d.day) + ' · ' + escapeHtml(d.calories) + ' kcal</p>';
      }).join('')) || '<p class="hint">No meals logged yet.</p>';
    }).catch(function () { if (todayBox) todayBox.textContent = 'Could not load today\'s log.'; });
  }
  var typeForm = document.getElementById('type-form');
  if (typeForm) typeForm.addEventListener('submit', function (evt) {
    evt.preventDefault(); scoreBarcode(document.getElementById('barcode').value);
  });
  var searchForm = document.getElementById('search-form');
  if (searchForm) searchForm.addEventListener('submit', function (evt) {
    evt.preventDefault();
    var q = (document.getElementById('q').value || '').trim();
    var box = document.getElementById('search-results');
    if (q.length < 3) { showError('Type at least 3 letters.'); return; }
    box.innerHTML = '<p class="hint">Searching…</p>';
    postJSON('/api/food-scan/search', { q: q }).then(function (data) {
      var items = (data && data.items) || [];
      if (!items.length) { box.innerHTML = '<p>No matches. Try a shorter name or a barcode.</p>'; return; }
      box.innerHTML = items.map(function (item) {
        return '<p><button type="button" class="btn btn-outline pick-code" data-code="' + escapeHtml(item.code) + '">' + escapeHtml(item.name) + '</button></p>';
      }).join('');
      box.querySelectorAll('.pick-code').forEach(function (b) {
        b.addEventListener('click', function () { scoreBarcode(b.getAttribute('data-code')); });
      });
    });
  });
  function decodeFromFile(file) {
    if (!file || typeof Quagga === 'undefined') { showError('Scanner library not ready. Refresh the page.'); return; }
    if (file.size > 8 * 1024 * 1024) { showError('That photo is larger than 8 MB.'); return; }
    showLoad('Reading barcode from photo…');
    Quagga.decodeSingle({
      src: URL.createObjectURL(file), numOfWorkers: 0, inputStream: { size: 1600 },
      decoder: { readers: ['upc_reader', 'upc_e_reader', 'ean_reader', 'ean_8_reader', 'code_128_reader'] }, locate: true
    }, function (result) {
      if (result && result.codeResult && result.codeResult.code) scoreBarcode(result.codeResult.code);
      else showError('Could not read bars in that photo. Fill the frame with only the barcode.');
    });
  }
  var snapBtn = document.getElementById('decode-barcode-photo');
  var snapInput = document.getElementById('barcode-photo');
  if (snapBtn && snapInput) snapBtn.addEventListener('click', function () {
    var file = snapInput.files && snapInput.files[0];
    if (!file) { showError('Choose or capture a barcode photo first.'); return; }
    decodeFromFile(file);
  });
  function bindPhoto(inputId, previewId, buttonId, clearId, url, loadingText) {
    var input = document.getElementById(inputId);
    var preview = document.getElementById(previewId);
    var button = document.getElementById(buttonId);
    var clearBtn = document.getElementById(clearId);
    if (input && preview) input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      if (!file) return;
      if (file.size > 8 * 1024 * 1024) { showError('That photo is larger than 8 MB.'); input.value = ''; return; }
      preview.src = URL.createObjectURL(file); preview.hidden = false;
    });
    if (clearBtn && input && preview) clearBtn.addEventListener('click', function () {
      input.value = ''; preview.removeAttribute('src'); preview.hidden = true;
    });
    if (button) button.addEventListener('click', function () {
      var file = input && input.files && input.files[0];
      if (!file) { showError('Choose or capture a photo first.'); return; }
      showLoad(loadingText);
      var reader = new FileReader();
      reader.onerror = function () { showError('Could not read that file.'); };
      reader.onload = function () {
        postJSON(url, { image_b64: String(reader.result || '').split(',')[1] || '', mime: file.type || 'image/jpeg' }).then(renderResult);
      };
      reader.readAsDataURL(file);
    });
  }
  bindPhoto('photo', 'preview', 'score-photo', 'clear-photo', '/api/food-scan/photo', 'Reading the label…');
  bindPhoto('plate', 'plate-preview', 'score-plate', 'clear-plate', '/api/food-scan/meal', 'Estimating the plate…');
  function onDetected(result) {
    if (result && result.codeResult && result.codeResult.code) scoreBarcode(result.codeResult.code);
  }
  function enableInlineVideo() {
    var video = document.querySelector('#reader video');
    if (!video) return;
    video.setAttribute('playsinline', 'true');
    video.setAttribute('webkit-playsinline', 'true');
    video.muted = true;
    video.setAttribute('muted', '');
    video.setAttribute('autoplay', '');
    video.playsInline = true;
    var play = video.play && video.play();
    if (play && play.catch) play.catch(function () {});
  }
  function cameraErrorText(err) {
    var name = (err && (err.name || err.message)) || '';
    if (/NotAllowed|Permission/i.test(name)) return 'Camera permission was blocked. Allow camera for this site, or use Type barcode / a photo.';
    if (/NotFound|DevicesNotFound/i.test(name)) return 'No camera was found. Use Type barcode or a photo instead.';
    return 'Camera failed on this phone. Use Type barcode or a close photo of the bars.';
  }
  var startCam = document.getElementById('start-cam');
  if (startCam) startCam.addEventListener('click', function () {
    if (typeof Quagga === 'undefined') { if (camStatus) camStatus.textContent = 'Scanner library not ready. Refresh the page.'; return; }
    if (running) return;
    running = true;
    if (camStatus) camStatus.textContent = 'Starting camera… allow access if the phone asks.';
    Quagga.init({
      inputStream: {
        type: 'LiveStream',
        target: document.getElementById('reader'),
        constraints: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      },
      locator: { patchSize: 'large', halfSample: false }, numOfWorkers: 0, frequency: 10,
      decoder: { readers: ['upc_reader', 'upc_e_reader', 'ean_reader', 'ean_8_reader', 'code_128_reader'] },
      locate: true
    }, function (err) {
      if (err) {
        running = false;
        if (camStatus) camStatus.textContent = cameraErrorText(err);
        return;
      }
      Quagga.start();
      enableInlineVideo();
      setTimeout(enableInlineVideo, 250);
      setTimeout(enableInlineVideo, 800);
      if (camStatus) camStatus.textContent = 'Hold the bars steady, about 4–6 inches from the camera.';
    });
    Quagga.offDetected(onDetected); Quagga.onDetected(onDetected);
  });
  var stopCam = document.getElementById('stop-cam');
  if (stopCam) stopCam.addEventListener('click', function () { running = false; try { Quagga.stop(); } catch (e) {} });
  if (loggedIn) { loadHistory(); loadDiary(); }
})();
