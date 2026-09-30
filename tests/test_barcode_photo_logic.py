"""Still-photo barcode decisions: empty upload vs unreadable vs no barcode vs HEIC."""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOGIC = os.path.join(ROOT, "static", "js", "barcode_photo_logic.js")


def _run(body):
    script = (
        "const Photo = require(%s);\n" % json.dumps(LOGIC)
        + body
        + "\nprocess.stdout.write(JSON.stringify(out));\n"
    )
    proc = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def test_empty_upload_is_not_a_missing_barcode():
    out = _run("""
      const out = {
        missing: Photo.barcodePhotoOutcome({ fileMeta: null }),
        empty: Photo.barcodePhotoOutcome({ fileMeta: { name: 'image.jpg', type: 'image/jpeg', size: 0 } }),
        bytesEmpty: Photo.barcodePhotoOutcome({ fileMeta: { name: 'image.jpg', type: 'image/jpeg', size: 10 }, byteLength: 0 }),
        noBarcode: Photo.barcodePhotoOutcome({
          fileMeta: { name: 'image.jpg', type: 'image/jpeg', size: 1200 },
          stage: 'decode', imageOpened: true, quaggaLoaded: true, code: ''
        }),
        found: Photo.barcodePhotoOutcome({
          fileMeta: { name: 'image.jpg', type: 'image/jpeg', size: 1200 },
          stage: 'decode', imageOpened: true, quaggaLoaded: true, code: '012345678905'
        })
      };
    """)
    assert out["missing"]["code"] == "missing"
    assert out["empty"]["code"] == "empty"
    assert out["bytesEmpty"]["code"] == "empty"
    assert "never uploaded" in out["empty"]["message"]
    assert out["noBarcode"]["code"] == "noBarcode"
    assert "No barcode in that photo" in out["noBarcode"]["message"]
    assert out["empty"]["message"] != out["noBarcode"]["message"]
    assert out["found"]["ok"] is True and out["found"]["barcode"] == "012345678905"


def test_heic_and_unreadable_and_library_failure():
    heic = bytes([0, 0, 0, 0x18, 0x66, 0x74, 0x79, 0x70, 0x68, 0x65, 0x69, 0x63])
    jpeg = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 8
    out = _run("""
      const heic = Uint8Array.from(%s);
      const jpeg = Uint8Array.from(%s);
      const out = {
        sniffHeic: Photo.sniffImageKind(heic),
        sniffJpeg: Photo.sniffImageKind(jpeg),
        heicClosed: Photo.barcodePhotoOutcome({
          fileMeta: { name: 'IMG_0001.HEIC', type: 'image/heic', size: 4000 },
          kind: 'heic', imageOpened: false, byteLength: 4000
        }),
        jpegClosed: Photo.barcodePhotoOutcome({
          fileMeta: { name: 'image.jpg', type: 'image/jpeg', size: 4000 },
          kind: 'jpeg', imageOpened: false, byteLength: 4000
        }),
        lib: Photo.barcodePhotoOutcome({
          fileMeta: { name: 'image.jpg', type: 'image/jpeg', size: 4000 },
          stage: 'decode', imageOpened: true, quaggaLoaded: false, code: ''
        }),
        timeout: Photo.barcodePhotoOutcome({
          fileMeta: { name: 'image.jpg', type: 'image/jpeg', size: 4000 },
          stage: 'decode', imageOpened: true, quaggaLoaded: true, timedOut: true
        }),
        reader: Photo.barcodePhotoOutcome({
          fileMeta: { name: 'image.jpg', type: 'image/jpeg', size: 4000 },
          stage: 'decode', imageOpened: true, quaggaLoaded: true, decodeError: true
        }),
        tooBig: Photo.classifyPhotoFile({ name: 'a.jpg', type: 'image/jpeg', size: Photo.MAX_BYTES + 1 }),
        stop: Photo.stillDecodeShouldStopLiveCamera(true),
        noStop: Photo.stillDecodeShouldStopLiveCamera(false)
      };
    """ % (list(heic), list(jpeg)))
    assert out["sniffHeic"] == "heic" and out["sniffJpeg"] == "jpeg"
    assert out["heicClosed"]["code"] == "heic"
    assert "HEIC" in out["heicClosed"]["message"]
    assert out["jpegClosed"]["code"] == "unreadable"
    assert out["heicClosed"]["message"] != out["jpegClosed"]["message"]
    assert out["lib"]["code"] == "lib"
    assert "failed to load" in out["lib"]["message"]
    assert out["timeout"]["code"] == "timeout"
    assert out["reader"]["code"] == "reader"
    assert out["tooBig"]["code"] == "tooBig"
    assert out["stop"] is True and out["noStop"] is False


def test_scanner_page_iphone_photo_hooks():
    html = open(os.path.join(ROOT, "templates", "food_scanner.html"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "static", "js", "food_scanner.js"), encoding="utf-8").read()
    assert "cdn.jsdelivr.net" not in html
    assert "vendor/quagga.min.js" in html
    assert "barcode_photo_logic.js" in html
    assert 'id="barcode-photo"' in html
    barcode_tag = html.split('id="barcode-photo"', 1)[1].split(">", 1)[0]
    assert "capture=" not in barcode_tag
    assert "image/heic" in barcode_tag
    assert "capture=" not in html
    assert "stopLiveCameraForPhoto" in js
    assert "Quagga.decodeSingle" in js
    assert "src: URL.createObjectURL" not in js
    assert "runQuaggaOnDataUrl" in js
    assert "No barcode in that photo" not in js  # wording lives in the helper, not a single generic path
    assert "barcodePhotoOutcome" in js
    assert os.path.isfile(os.path.join(ROOT, "static", "js", "vendor", "quagga.min.js"))
