/* Pure decisions for the Food Scanner still-photo barcode path. No DOM. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.RCBarcodePhoto = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  var MAX_BYTES = 8 * 1024 * 1024;
  var MESSAGES = {
    missing: 'No photo was uploaded. Choose a photo and try again.',
    empty: 'The photo never uploaded (the file is empty). Choose it again. If it is in iCloud, open it in Photos first, then choose it again.',
    tooBig: 'That photo is larger than 8 MB. Use a smaller photo of the barcode.',
    heic: 'This photo is HEIC/HEIF and this browser could not open it. Retake it as JPEG, or choose a JPEG, PNG, or WEBP.',
    unreadable: 'The photo uploaded but could not be opened. Use a JPEG, PNG, WEBP, or HEIC image.',
    noBarcode: 'No barcode in that photo. Fill the frame with only the barcode.',
    libMissing: 'Barcode scanner library failed to load. Refresh the page. You can still type the barcode.',
    cameraLib: 'Barcode scanner library failed to load, so the live camera cannot start. Refresh the page, or type the barcode.',
    scannerFailed: 'The photo uploaded, but the barcode reader failed on it. Try a closer JPEG of the bars only, or type the digits.',
    decodeHung: 'The photo uploaded, but the scanner did not finish reading it. Try a smaller JPEG of the bars only.'
  };

  function extOf(name) {
    var n = String(name || '').toLowerCase();
    var i = n.lastIndexOf('.');
    return i >= 0 ? n.slice(i) : '';
  }

  function isHeic(meta) {
    var type = String((meta && meta.type) || '').toLowerCase();
    var ext = extOf(meta && meta.name);
    return type === 'image/heic' || type === 'image/heif' ||
      type === 'image/heic-sequence' || type === 'image/heif-sequence' ||
      ext === '.heic' || ext === '.heif';
  }

  function sniffImageKind(bytes) {
    if (!bytes || bytes.length < 12) return 'unknown';
    function at(i) { return bytes[i]; }
    if (at(0) === 0xFF && at(1) === 0xD8 && at(2) === 0xFF) return 'jpeg';
    if (at(0) === 0x89 && at(1) === 0x50 && at(2) === 0x4E && at(3) === 0x47) return 'png';
    if (at(0) === 0x52 && at(1) === 0x49 && at(2) === 0x46 && at(3) === 0x46 &&
        at(8) === 0x57 && at(9) === 0x45 && at(10) === 0x42 && at(11) === 0x50) return 'webp';
    if (at(4) === 0x66 && at(5) === 0x74 && at(6) === 0x79 && at(7) === 0x70) {
      var brand = '';
      for (var i = 8; i < 12; i++) brand += String.fromCharCode(at(i));
      if (brand === 'avif') return 'avif';
      if ({ heic: 1, heix: 1, hevc: 1, hevx: 1, heim: 1, heis: 1, heif: 1, mif1: 1, msf1: 1 }[brand]) return 'heic';
    }
    return 'unknown';
  }

  function classifyPhotoFile(meta) {
    if (!meta) return { ok: false, code: 'missing', message: MESSAGES.missing };
    var size = Number(meta.size);
    if (!isFinite(size) || size < 0) return { ok: false, code: 'missing', message: MESSAGES.missing };
    if (size === 0) return { ok: false, code: 'empty', message: MESSAGES.empty };
    if (size > MAX_BYTES) return { ok: false, code: 'tooBig', message: MESSAGES.tooBig };
    return { ok: true, code: 'ready', heic: isHeic(meta), message: '' };
  }

  function messageForUndecodable(meta, kind) {
    if (isHeic(meta) || kind === 'heic') return MESSAGES.heic;
    return MESSAGES.unreadable;
  }

  /* Quagga2 publishes live frames and still-photo frames on one global "processed"
     bus. decodeSingle takes the next event, so a running camera must be stopped
     first or the upload is never the image that gets read. */
  function stillDecodeShouldStopLiveCamera(cameraRunning) {
    return !!cameraRunning;
  }

  function barcodePhotoOutcome(opts) {
    opts = opts || {};
    var meta = opts.fileMeta;
    if (!meta) return { ok: false, code: 'missing', message: MESSAGES.missing };
    var size = Number(meta.size);
    if ((!isFinite(size) || size <= 0) && opts.byteLength > 0) size = opts.byteLength;
    var verdict = classifyPhotoFile({ name: meta.name, type: meta.type, size: size });
    if (!verdict.ok) return { ok: false, code: verdict.code, message: verdict.message };
    if (opts.readFailed) return { ok: false, code: 'unreadable', message: MESSAGES.unreadable };
    if (opts.byteLength === 0) return { ok: false, code: 'empty', message: MESSAGES.empty };
    var kind = opts.kind || (opts.bytes ? sniffImageKind(opts.bytes) : '');
    if (opts.imageOpened === false) {
      var heic = kind === 'heic' || isHeic(meta);
      return { ok: false, code: heic ? 'heic' : 'unreadable', message: messageForUndecodable(meta, heic ? 'heic' : kind) };
    }
    if (opts.stage === 'decode') {
      var digits = String(opts.code || '').replace(/\D+/g, '');
      if (opts.quaggaLoaded === false) {
        if (digits.length >= 8) return { ok: true, code: 'found', barcode: digits };
        return { ok: false, code: 'lib', message: MESSAGES.libMissing };
      }
      if (opts.timedOut) return { ok: false, code: 'timeout', message: MESSAGES.decodeHung };
      if (opts.decodeError) return { ok: false, code: 'reader', message: MESSAGES.scannerFailed };
      if (digits.length >= 8) return { ok: true, code: 'found', barcode: digits };
      return { ok: false, code: 'noBarcode', message: MESSAGES.noBarcode };
    }
    return { ok: true, code: 'ready', kind: kind, heic: kind === 'heic' || isHeic(meta) };
  }

  return {
    MAX_BYTES: MAX_BYTES,
    MESSAGES: MESSAGES,
    isHeic: isHeic,
    sniffImageKind: sniffImageKind,
    classifyPhotoFile: classifyPhotoFile,
    messageForUndecodable: messageForUndecodable,
    stillDecodeShouldStopLiveCamera: stillDecodeShouldStopLiveCamera,
    barcodePhotoOutcome: barcodePhotoOutcome
  };
});
