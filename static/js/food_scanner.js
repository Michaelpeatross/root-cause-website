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
  var lastCode = ''; var lastAt = 0; var running = false; var lookupBusy = false;
  var lastFood = null;
  function escapeHtml(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
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
  function postJSON(url, body, timeoutMs) {
    var opts = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    var timer;
    if (timeoutMs && typeof AbortController === 'function') {
      var ctrl = new AbortController();
      opts.signal = ctrl.signal;
      timer = setTimeout(function () { ctrl.abort(); }, timeoutMs);
    }
    return fetch(url, opts).then(function (res) {
      if (timer) clearTimeout(timer);
      return res.json().catch(function () { return { ok: false, error: 'No result returned.' }; });
    }).catch(function (err) {
      if (timer) clearTimeout(timer);
      if (err && err.name === 'AbortError') return { ok: false, error: 'That estimate took too long. Try a closer photo of the Nutrition Facts panel.' };
      return { ok: false, error: 'The request did not finish. Check your connection and try again.' };
    });
  }
  function intakeButton(data) {
    if (!loggedIn || !data) return '';
    if (data.saved) return '<p class="hint">Added to today\'s intake.</p>';
    return '<p><button type="button" class="btn btn-primary" id="add-this-intake">Add to today\'s intake</button></p>';
  }
  function mealFromResult(data) {
    var p = (data && data.product) || {};
    var r = (data && data.rating) || {};
    var m = (data && data.macros) || {};
    return {
      name: p.name || '',
      code: p.code || '',
      calories: m.calories,
      protein: m.protein,
      carbs: m.carbs,
      fat: m.fat,
      sugar: m.sugar,
      fiber: m.fiber,
      sodium: m.sodium,
      score: r.score,
      label: r.label || ''
    };
  }
  function addIntake(payload, button) {
    if (button) { button.disabled = true; button.textContent = 'Adding…'; }
    postJSON('/api/food-scan/intake', payload).then(function (data) {
      if (!data || !data.ok) {
        if (button) { button.disabled = false; button.textContent = 'Add to today'; }
        showError((data && data.error) || 'Could not add that to today.');
        return;
      }
      if (button) { button.textContent = 'Added'; }
      loadDiary();
    });
  }
  function renderResult(data) {
    if (!data || !data.ok) { showError((data && data.error) || 'Could not estimate that item.'); return; }
    var p = data.product || {}; var r = data.rating || {}; var m = data.macros || {};
    var guestNote = data.guest ? '<p class="guest-cta">Create a free account to save this estimate and add it to today\'s intake.</p>' : intakeButton(data);
    lastFood = data;
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="card">' +
      (r.score != null ? '<div class="score-ring" style="background:' + escapeHtml(r.color || '#555') + '"><div class="num">' + escapeHtml(r.score) + '</div><div>' + escapeHtml(r.label || '') + '</div></div>' : '') +
      '<h2>' + escapeHtml(p.name || 'Food') + '</h2>' +
      (r.processing_label ? '<p><strong>' + escapeHtml(r.processing_label) + '</strong></p>' : '') +
      ((r.reasons || []).length ? '<ul class="score-reasons">' + r.reasons.map(function (x) { return '<li>' + escapeHtml(x) + '</li>'; }).join('') + '</ul>' : '') +
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
      guestNote +
      '<p><button type="button" class="btn btn-outline" id="scan-another">Scan another</button></p></div>';
    var addBtn = document.getElementById('add-this-intake');
    if (addBtn) addBtn.addEventListener('click', function () { addIntake(mealFromResult(data), addBtn); });
    var again = document.getElementById('scan-another');
    if (again) again.addEventListener('click', function () {
      var start = document.getElementById('start-cam');
      if (start) start.click();
      var reader = document.getElementById('reader');
      if (reader && reader.scrollIntoView) reader.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    if (resultEl.scrollIntoView) resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (loggedIn) { loadHistory(); loadDiary(); }
  }
  function scoreBarcode(code) {
    var digits = String(code || '').replace(/\D+/g, '');
    if (digits.length < 8) { showError('Enter at least 8 barcode digits.'); return; }
    var now = Date.now();
    if (lookupBusy) return;
    if (digits === lastCode && now - lastAt < 4000) return;
    lastCode = digits; lastAt = now;
    lookupBusy = true;
    stopLiveCameraForPhoto();
    if (camStatus) camStatus.textContent = 'Found ' + digits + '. Camera paused.';
    showLoad('Found ' + digits + '. Looking it up…');
    postJSON('/api/food-scan/barcode', { barcode: digits }).then(function (data) {
      lookupBusy = false;
      renderResult(data);
    });
  }
  function loadHistory() {
    var box = document.getElementById('history-list'); if (!box) return;
    fetch('/api/food-scan/history').then(function (r) { return r.json(); }).then(function (data) {
      var items = (data && data.items) || [];
      if (!items.length) { box.innerHTML = '<p class="hint">No scans saved yet.</p>'; return; }
      box.innerHTML = items.map(function (item, idx) {
        var canAdd = item.code || item.calories != null;
        var add = canAdd
          ? '<button type="button" class="btn btn-outline add-intake" data-idx="' + idx + '">Add to today</button>'
          : '';
        var del = '<button type="button" class="btn btn-outline del-scan" data-idx="' + idx + '">Delete</button>';
        return '<div class="hist-row"><div><strong>' + escapeHtml(item.name) + '</strong>' +
          '<div class="meta">Score ' + escapeHtml(item.score == null ? '—' : item.score) +
          (item.calories != null ? ' · ' + escapeHtml(item.calories) + ' kcal' : '') +
          '<br>' + escapeHtml(item.scanned_at || '') + '</div></div>' +
          '<div style="display:flex;flex-direction:column;gap:.35rem;">' + add + del + '</div></div>';
      }).join('');
      box.querySelectorAll('.add-intake').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var item = items[Number(btn.getAttribute('data-idx'))] || {};
          addIntake({
            name: item.name || '',
            code: item.code || '',
            calories: item.calories,
            protein: item.protein,
            carbs: item.carbs,
            fat: item.fat,
            sugar: item.sugar,
            fiber: item.fiber,
            sodium: item.sodium,
            score: item.score,
            label: item.label || ''
          }, btn);
        });
      });
      box.querySelectorAll('.del-scan').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var item = items[Number(btn.getAttribute('data-idx'))] || {};
          if (!item.id) return;
          if (!window.confirm('Remove ' + (item.name || 'this scan') + ' from scan history?')) return;
          btn.disabled = true;
          postJSON('/api/food-scan/history/delete', { id: item.id }).then(function (res) {
            if (!res || !res.ok) {
              btn.disabled = false;
              showError((res && res.error) || 'Could not delete that scan.');
              return;
            }
            loadHistory();
          });
        });
      });
    }).catch(function () { box.textContent = 'Could not load history.'; });
  }
  function loadDiary() {
    var todayBox = document.getElementById('diary-today');
    var daysBox = document.getElementById('diary-days');
    if (!todayBox && !daysBox) return;
    fetch('/api/food-scan/diary').then(function (r) { return r.json(); }).then(function (data) {
      var today = (data && data.today) || {};
      if (todayBox) todayBox.innerHTML = '<p><strong>' + (today.meals || 0) + ' meals · ' + (today.calories || 0) + ' kcal</strong></p>';
      var meals = (data && data.meals) || [];
      var todayMeals = meals.filter(function (m) { return (m.day || '').slice(0, 10) === (today.day || ''); });
      if (todayBox && todayMeals.length) {
        todayBox.innerHTML += todayMeals.map(function (m) {
          return '<div class="log-row"><div><strong>' + escapeHtml(m.name) + '</strong><div class="meta">' +
            escapeHtml(m.calories == null ? '—' : m.calories) + ' kcal</div></div></div>';
        }).join('');
      }
      if (daysBox) {
        var days = data.days || [];
        daysBox.innerHTML = days.length ? days.map(function (d) {
          return '<div class="log-row"><div><strong>' + escapeHtml(d.day) + '</strong><div class="meta">' +
            escapeHtml(d.meals) + ' meals · ' + escapeHtml(d.calories) + ' kcal</div></div></div>';
        }).join('') : '<p class="hint">No meals logged yet. Use Add to today on a scan.</p>';
      }
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
  function photoMessages() {
    return (window.RCBarcodePhoto && window.RCBarcodePhoto.MESSAGES) || {
      missing: 'No photo was uploaded. Choose a barcode photo and try again.',
      unreadable: 'The photo uploaded but could not be opened. Use a JPEG, PNG, WEBP, or HEIC image.',
      libMissing: 'Barcode scanner library failed to load. Refresh the page. You can still type the barcode.',
      cameraLib: 'Barcode scanner library failed to load, so the live camera cannot start. Refresh the page, or type the barcode.'
    };
  }
  function readArrayBuffer(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onerror = function () { reject(new Error('read')); };
      reader.onload = function () { resolve(reader.result); };
      reader.readAsArrayBuffer(file);
    });
  }
  function bufferToDataUrl(buf, mime) {
    return new Promise(function (resolve, reject) {
      var blob = new Blob([buf], { type: mime || 'image/jpeg' });
      var reader = new FileReader();
      reader.onerror = function () { reject(new Error('read')); };
      reader.onload = function () { resolve(String(reader.result || '')); };
      reader.readAsDataURL(blob);
    });
  }
  function loadImageElement(blob) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(blob);
      var img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        if (!img.naturalWidth || !img.naturalHeight) reject(new Error('unreadable'));
        else resolve(img);
      };
      img.onerror = function () {
        URL.revokeObjectURL(url);
        reject(new Error('unreadable'));
      };
      img.src = url;
    });
  }
  function imageToJpegDataUrl(img) {
    var maxSide = 1600;
    var scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
    var w = Math.max(1, Math.round(img.naturalWidth * scale));
    var h = Math.max(1, Math.round(img.naturalHeight * scale));
    var canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    var ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, w, h);
    var dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    if (!dataUrl || dataUrl.indexOf('data:image') !== 0) throw new Error('unreadable');
    return dataUrl;
  }
  function nativeDetect(img) {
    if (typeof window.BarcodeDetector !== 'function') return Promise.resolve('');
    var detector;
    try { detector = new window.BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39'] }); }
    catch (e1) {
      try { detector = new window.BarcodeDetector(); }
      catch (e2) { return Promise.resolve(''); }
    }
    return detector.detect(img).then(function (codes) {
      var raw = codes && codes[0] && (codes[0].rawValue || '');
      return String(raw || '');
    }).catch(function () { return ''; });
  }
  function runQuaggaOnDataUrl(dataUrl) {
    return new Promise(function (resolve, reject) {
      var settled = false;
      function finish(result, isErr) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (isErr) reject(result instanceof Error ? result : new Error('decode'));
        else resolve(result);
      }
      var timer = setTimeout(function () { finish(new Error('timeout'), true); }, 12000);
      try {
        var pending = Quagga.decodeSingle({
          src: dataUrl,
          numOfWorkers: 0,
          inputStream: { size: 1600 },
          decoder: { readers: ['upc_reader', 'upc_e_reader', 'ean_reader', 'ean_8_reader', 'code_128_reader'] },
          locate: true
        }, function (result) { finish(result, false); });
        if (pending && typeof pending.then === 'function') {
          pending.then(function (result) { finish(result, false); }).catch(function (err) { finish(err, true); });
        }
      } catch (err) {
        finish(err, true);
      }
    });
  }
  /* Live camera and decodeSingle share Quagga's global "processed" bus.
     Stop the camera before a still photo or the next camera frame (often not
     the barcode) is what gets reported. */
  function stopLiveCameraForPhoto() {
    var wasRunning = running;
    running = false;
    if (typeof Quagga === 'undefined') return Promise.resolve(wasRunning);
    try { Quagga.offDetected(onDetected); } catch (e) {}
    try {
      var stopped = Quagga.stop();
      if (stopped && typeof stopped.then === 'function') {
        return stopped.then(function () { return wasRunning; }, function () { return wasRunning; });
      }
    } catch (e2) {}
    return Promise.resolve(wasRunning);
  }
  var pendingBarcodeFile = null;
  function showBarcodePreview(blob) {
    var preview = document.getElementById('barcode-preview');
    if (!preview) return;
    if (preview._rcUrl) URL.revokeObjectURL(preview._rcUrl);
    var url = URL.createObjectURL(blob);
    preview._rcUrl = url;
    preview.src = url;
    preview.hidden = false;
  }
  function decodeFromFile(file) {
    var Photo = window.RCBarcodePhoto;
    if (!Photo) { showError(photoMessages().libMissing); return; }
    var gate = Photo.barcodePhotoOutcome({ fileMeta: file || null });
    if (!gate.ok) { showError(gate.message); return; }
    showLoad('Reading barcode from photo…');
    var handled = function (err) { err.handled = true; return Promise.reject(err); };
    // Start the read in this turn. iOS can drop the file if the input is cleared first.
    var readPromise = readArrayBuffer(file);
    stopLiveCameraForPhoto().then(function (wasRunning) {
      if (wasRunning && camStatus) camStatus.textContent = 'Camera paused to read the photo.';
      return readPromise;
    }).then(function (buf) {
      var bytes = new Uint8Array(buf || new ArrayBuffer(0));
      var kind = Photo.sniffImageKind(bytes);
      var afterRead = Photo.barcodePhotoOutcome({ fileMeta: file, byteLength: bytes.length, kind: kind });
      if (!afterRead.ok) { showError(afterRead.message); return handled(new Error('read')); }
      var mime = kind === 'png' ? 'image/png' : (kind === 'webp' ? 'image/webp' : (kind === 'jpeg' ? 'image/jpeg' : (file.type || 'image/jpeg')));
      var blob = new Blob([buf], { type: mime });
      showBarcodePreview(blob);
      return loadImageElement(blob).then(function (img) {
        return { img: img, buf: buf, kind: kind, mime: mime };
      }, function () {
        var fail = Photo.barcodePhotoOutcome({ fileMeta: file, byteLength: bytes.length, kind: kind, imageOpened: false });
        showError(fail.message);
        return handled(new Error('open'));
      });
    }).then(function (info) {
      return nativeDetect(info.img).then(function (nativeCode) {
        if (nativeCode) return { code: nativeCode, quaggaLoaded: typeof Quagga !== 'undefined' };
        if (typeof Quagga === 'undefined') return { code: '', quaggaLoaded: false };
        var dataPromise = (info.kind === 'heic' || Photo.isHeic(file))
          ? Promise.resolve().then(function () { return imageToJpegDataUrl(info.img); })
          : bufferToDataUrl(info.buf, info.mime);
        return dataPromise.then(function (dataUrl) {
          return runQuaggaOnDataUrl(dataUrl).then(function (result) {
            var code = result && result.codeResult && result.codeResult.code;
            return { code: code || '', quaggaLoaded: true };
          }, function (err) {
            var timedOut = !!(err && err.message === 'timeout');
            return { code: '', quaggaLoaded: true, timedOut: timedOut, decodeError: !timedOut };
          });
        });
      });
    }).then(function (decoded) {
      var outcome = Photo.barcodePhotoOutcome({
        fileMeta: file,
        stage: 'decode',
        imageOpened: true,
        quaggaLoaded: decoded.quaggaLoaded !== false,
        code: decoded.code,
        decodeError: !!decoded.decodeError,
        timedOut: !!decoded.timedOut
      });
      if (outcome.ok) scoreBarcode(outcome.barcode);
      else showError(outcome.message);
    }).catch(function (err) {
      if (err && err.handled) return;
      showError(photoMessages().unreadable);
    });
  }
  function takeChosenFile(input) {
    var file = input.files && input.files[0];
    if (!file) return null;
    var stamp = [file.name, file.size, file.lastModified, file.type].join(':');
    if (input._rcStamp === stamp) return null;
    input._rcStamp = stamp;
    setTimeout(function () {
      try { input.value = ''; } catch (e) {}
    }, 0);
    setTimeout(function () { if (input._rcStamp === stamp) input._rcStamp = ''; }, 1500);
    return file;
  }
  var snapBtn = document.getElementById('decode-barcode-photo');
  var snapInput = document.getElementById('barcode-photo');
  function onBarcodePicked() {
    var file = takeChosenFile(snapInput);
    if (!file) return;
    pendingBarcodeFile = file;
    decodeFromFile(file);
  }
  if (snapInput) {
    snapInput.addEventListener('change', onBarcodePicked);
    snapInput.addEventListener('input', onBarcodePicked);
  }
  if (snapBtn) snapBtn.addEventListener('click', function () {
    if (!pendingBarcodeFile) { showError(photoMessages().missing); return; }
    decodeFromFile(pendingBarcodeFile);
  });
  // App Store Guideline 5.1.2(i): ask before sending personal data (photos) to a third-party AI.
  function aiConsentOk() {
    try { if (window.localStorage.getItem('rc_ai_photo_consent') === 'yes') return true; } catch (e) {}
    var ok = window.confirm('To read this photo, it is sent to Root Cause and our AI provider (xAI) for analysis. The photo is not stored after the result comes back. See our Privacy Policy for details. Continue?');
    if (ok) { try { window.localStorage.setItem('rc_ai_photo_consent', 'yes'); } catch (e) {} }
    return ok;
  }
  var pickedFiles = {};
  function payloadFromFile(file) {
    var Photo = window.RCBarcodePhoto;
    if (Photo && Photo.isHeic(file)) {
      return readArrayBuffer(file).then(function (buf) {
        var bytes = new Uint8Array(buf || new ArrayBuffer(0));
        var kind = Photo.sniffImageKind(bytes);
        if (!bytes.length) {
          var emptyErr = new Error('empty');
          emptyErr.userMessage = Photo.MESSAGES.empty;
          throw emptyErr;
        }
        var blob = new Blob([buf], { type: file.type || 'image/heic' });
        return loadImageElement(blob).then(imageToJpegDataUrl).then(function (dataUrl) {
          return { b64: String(dataUrl).split(',')[1] || '', mime: 'image/jpeg' };
        }).catch(function (err) {
          if (err && err.userMessage) throw err;
          var heicErr = new Error('heic');
          heicErr.userMessage = Photo.messageForUndecodable(file, kind === 'heic' ? 'heic' : 'heic');
          throw heicErr;
        });
      });
    }
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onerror = function () { reject(new Error('read')); };
      reader.onload = function () {
        resolve({ b64: String(reader.result || '').split(',')[1] || '', mime: file.type || 'image/jpeg' });
      };
      reader.readAsDataURL(file);
    });
  }
  function bindPhoto(inputId, previewId, buttonId, clearId, url, loadingText) {
    var input = document.getElementById(inputId);
    var preview = document.getElementById(previewId);
    var button = document.getElementById(buttonId);
    var clearBtn = document.getElementById(clearId);
    function onPick() {
      var file = takeChosenFile(input);
      if (!file) return;
      var Photo = window.RCBarcodePhoto;
      var verdict = Photo ? Photo.classifyPhotoFile(file) : { ok: file.size > 0 && file.size <= 8 * 1024 * 1024, message: 'That photo is larger than 8 MB.' };
      if (!verdict.ok) {
        showError(verdict.message || photoMessages().unreadable);
        pickedFiles[inputId] = null;
        return;
      }
      pickedFiles[inputId] = file;
      if (preview) { preview.src = URL.createObjectURL(file); preview.hidden = false; }
    }
    if (input) {
      input.addEventListener('change', onPick);
      input.addEventListener('input', onPick);
    }
    if (clearBtn && input && preview) clearBtn.addEventListener('click', function () {
      input.value = '';
      pickedFiles[inputId] = null;
      preview.removeAttribute('src');
      preview.hidden = true;
    });
    if (button) button.addEventListener('click', function () {
      var file = pickedFiles[inputId];
      if (!file) { showError(photoMessages().missing); return; }
      if (!aiConsentOk()) { showError('Photo analysis needs your OK to send the photo to our AI provider. You can still scan barcodes or search by name.'); return; }
      showLoad(loadingText);
      payloadFromFile(file).then(function (payload) {
        if (!payload.b64) { showError(photoMessages().unreadable); return; }
        postJSON(url, { image_b64: payload.b64, mime: payload.mime || 'image/jpeg' }, 50000).then(renderResult);
      }).catch(function (err) {
        showError((err && err.userMessage) || photoMessages().unreadable);
      });
    });
  }
  bindPhoto('photo', 'preview', 'score-photo', 'clear-photo', '/api/food-scan/photo', 'Reading the label…');
  bindPhoto('plate', 'plate-preview', 'score-plate', 'clear-plate', '/api/food-scan/meal', 'Estimating the plate…');
  var quickBtn = document.getElementById('quick-photo-btn');
  var quickInput = document.getElementById('quick-photo');
  if (quickBtn && quickInput) {
    quickBtn.addEventListener('click', function () { quickInput.click(); });
    quickInput.addEventListener('change', function () {
      var file = takeChosenFile(quickInput);
      if (!file) return;
      if (!aiConsentOk()) { showError('Photo analysis needs your OK to send the photo to our AI provider. You can still scan a barcode or search by name.'); return; }
      stopLiveCameraForPhoto();
      if (camStatus) camStatus.textContent = 'Camera paused. Reading the picture…';
      showLoad('Reading the picture and saving the estimate…');
      payloadFromFile(file).then(function (payload) {
        if (!payload.b64) { showError(photoMessages().unreadable); return; }
        postJSON('/api/food-scan/photo', { image_b64: payload.b64, mime: payload.mime || 'image/jpeg' }, 50000).then(renderResult);
      }).catch(function (err) {
        showError((err && err.userMessage) || photoMessages().unreadable);
      });
    });
  }
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
  function noteCamera(msg, asError) {
    if (camStatus) camStatus.textContent = msg;
    if (asError) showError(msg);
  }
  if (window.RC_QUAGGA_FAILED || typeof Quagga === 'undefined') {
    noteCamera(photoMessages().cameraLib, true);
  }
  var startCam = document.getElementById('start-cam');
  if (startCam) startCam.addEventListener('click', function () {
    if (typeof Quagga === 'undefined') { noteCamera(photoMessages().cameraLib, true); return; }
    if (running) return;
    running = true;
    if (camStatus) camStatus.textContent = 'Starting camera… allow access if the phone asks.';
    try { Quagga.init({
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
        noteCamera(cameraErrorText(err), true);
        return;
      }
      Quagga.start();
      enableInlineVideo();
      setTimeout(enableInlineVideo, 250);
      setTimeout(enableInlineVideo, 800);
      if (camStatus) camStatus.textContent = 'Hold the bars steady, about 4–6 inches from the camera.';
    });
    Quagga.offDetected(onDetected); Quagga.onDetected(onDetected);
    } catch (err) {
      running = false;
      noteCamera(cameraErrorText(err), true);
    }
  });
  var stopCam = document.getElementById('stop-cam');
  if (stopCam) stopCam.addEventListener('click', function () { running = false; try { Quagga.stop(); } catch (e) {} });
  if (loggedIn) { loadHistory(); loadDiary(); }
})();
