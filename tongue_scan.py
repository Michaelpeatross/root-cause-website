"""Tongue Scanner for the Root Cause Health App.

Photo in -> visible tongue features -> five-dimension wellness profile with
plain-language observations and gentle lifestyle ideas. Wellness education only,
never a diagnosis. Logged-in users can save scans to compare over time.
"""
import json, os, re, time, hashlib
from datetime import datetime

try:
    from central_time import central_now
except Exception:  # pragma: no cover
    central_now = datetime.now
try:
    from persistent_storage import setup_persistent_paths
    _PATHS = setup_persistent_paths(os.path.dirname(os.path.abspath(__file__)))
    HISTORY_DIR = os.path.join(_PATHS.get('data_dir') or os.path.dirname(os.path.abspath(__file__)), 'tongue_scans')
except Exception:
    HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'tongue_scans')

DISCLAIMER = (
    'Wellness education only, not medical advice. It does not diagnose, treat, or confirm any condition. '
    'See a dentist or doctor for anything that worries you, such as a sore that lasts more than two weeks, '
    'white or red patches, a lump, bleeding, or pain.'
)
OBS_NOTE = "Visible features from your scan. They don't confirm symptoms or nutrient deficiencies."

PROMPT = (
    'You are describing the visible appearance of a tongue in a photo for a general wellness education app. '
    'Do not diagnose or name any disease or deficiency. First decide whether the photo clearly shows a real human '
    'tongue sticking out of a mouth. If it is not a tongue (food, an object, a face without the tongue out, a drawing, '
    'an animal, a screen), set is_tongue false. If it is a tongue but too dark, blurry, small, or covered by a heavy '
    'color filter to read, set quality "poor". Lipstick-like filters or colored candy staining should be noted in quality_note. '
    'Describe only what is visible. Use exactly these options:\n'
    'body_color: "pink" (light red, typical), "pale", "red", "dark_red", "purplish"\n'
    'coating_thickness: "thin" (can see the tongue through it), "none" (bare, shiny), "thick", "patchy" (map-like or peeled areas)\n'
    'coating_color: "white", "yellow", "grey", "brown_black", "none"\n'
    'swelling: "none", "mild", "noticeable" (tongue looks puffy or wide, filling the mouth)\n'
    'tooth_marks: "none", "mild", "noticeable" (scalloped wavy edges along the sides)\n'
    'thin_body: true/false (tongue looks unusually thin or narrow)\n'
    'cracks: "none", "few", "many" (fissures or grooves on the surface; a single center line counts as few)\n'
    'red_dots: true/false (raised red dots or prickles, especially at tip or edges)\n'
    'moisture: "normal", "dry", "wet" (very wet, glossy with saliva pooling)\n'
    'tip_red: true/false (tip noticeably redder than the rest)\n'
    'spot_of_concern: true/false (any distinct sore, ulcer, lump, or a white or red patch that does not wipe like coating)\n'
    'Return JSON only: {"is_tongue":true,"quality":"good|ok|poor","quality_note":"short",'
    '"body_color":"","coating_thickness":"","coating_color":"","swelling":"","tooth_marks":"","thin_body":false,'
    '"cracks":"","red_dots":false,"moisture":"","tip_red":false,"spot_of_concern":false,'
    '"summary":"one or two friendly neutral sentences describing what is visible, no health claims"}'
)

_OPTS = {
    'body_color': ('pink', 'pale', 'red', 'dark_red', 'purplish'),
    'coating_thickness': ('thin', 'none', 'thick', 'patchy'),
    'coating_color': ('white', 'yellow', 'grey', 'brown_black', 'none'),
    'swelling': ('none', 'mild', 'noticeable'),
    'tooth_marks': ('none', 'mild', 'noticeable'),
    'cracks': ('none', 'few', 'many'),
    'moisture': ('normal', 'dry', 'wet'),
}
_DEFAULTS = {'body_color': 'pink', 'coating_thickness': 'thin', 'coating_color': 'white', 'swelling': 'none',
             'tooth_marks': 'none', 'cracks': 'none', 'moisture': 'normal'}

LABELS = {
    'body_color': {'pink': 'Pink body', 'pale': 'Pale body', 'red': 'Red body', 'dark_red': 'Deep red body',
                   'purplish': 'Purplish tone'},
    'coating_thickness': {'thin': 'Thin coating', 'none': 'Little to no coating', 'thick': 'Thick coating',
                          'patchy': 'Patchy coating'},
    'coating_color': {'white': 'White coating', 'yellow': 'Yellow coating', 'grey': 'Grey coating',
                      'brown_black': 'Dark coating', 'none': 'Clear surface'},
}


def _parse_json(raw):
    if not raw:
        return None
    raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    raw = re.sub(r'\s*```$', '', raw)
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r'\{.*\}', raw, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def _vision(image_b64, mime):
    try:
        from health_advisor import _grok_vision_chat
    except Exception:
        return None
    raw = _grok_vision_chat(
        [{'type': 'text', 'text': PROMPT},
         {'type': 'image_url', 'image_url': {'url': 'data:%s;base64,%s' % (mime, image_b64), 'detail': 'high'}}],
        system='Return valid JSON only. Describe visible appearance only. Never diagnose.',
        temperature=0.1,
        timeout=55,
    )
    return _parse_json(raw)


def _bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ('true', 'yes', '1')


def normalize_features(data):
    f = {}
    for key, opts in _OPTS.items():
        v = re.sub(r'[\s-]+', '_', str((data or {}).get(key) or '').strip().lower())
        if v == 'light_red':
            v = 'pink'
        if v in ('gray',):
            v = 'grey'
        if v in ('black', 'brown'):
            v = 'brown_black'
        f[key] = v if v in opts else _DEFAULTS[key]
    for key in ('thin_body', 'red_dots', 'tip_red', 'spot_of_concern'):
        f[key] = _bool((data or {}).get(key))
    return f


def _clamp(n):
    return max(30, min(100, int(round(n))))


def score_features(f):
    """Five 0-100 'visual balance' scores. 100 = typical, even appearance."""
    body = {'pink': 100, 'pale': 70, 'red': 72, 'dark_red': 55, 'purplish': 50}[f['body_color']]
    if f['tip_red'] and f['body_color'] == 'pink':
        body -= 8
    ccolor = {'white': 100, 'none': 92, 'yellow': 65, 'grey': 52, 'brown_black': 45}[f['coating_color']]
    if f['coating_color'] == 'white' and f['coating_thickness'] == 'thick':
        ccolor -= 12
    coat = {'thin': 100, 'none': 72, 'thick': 60, 'patchy': 68}[f['coating_thickness']]
    shape = 100 - {'none': 0, 'mild': 12, 'noticeable': 25}[f['swelling']] \
        - {'none': 0, 'mild': 10, 'noticeable': 20}[f['tooth_marks']] - (15 if f['thin_body'] else 0)
    surface = 100 - {'none': 0, 'few': 10, 'many': 28}[f['cracks']] - (10 if f['red_dots'] else 0) \
        - {'normal': 0, 'dry': 15, 'wet': 10}[f['moisture']]
    dims = [
        {'key': 'body_color', 'label': 'Body color', 'score': _clamp(body)},
        {'key': 'coating_color', 'label': 'Coating color', 'score': _clamp(ccolor)},
        {'key': 'coating', 'label': 'Coating', 'score': _clamp(coat)},
        {'key': 'shape', 'label': 'Shape', 'score': _clamp(shape)},
        {'key': 'surface', 'label': 'Surface', 'score': _clamp(surface)},
    ]
    overall = int(round(sum(d['score'] for d in dims) / len(dims)))
    return dims, overall


def _band(score):
    if score >= 85:
        return 'Well balanced'
    if score >= 70:
        return 'Mostly balanced'
    if score >= 55:
        return 'A few things to watch'
    return 'Worth some extra care'


def observations(f):
    """Pill tags plus the friendly detail rows (color, coating, shape, cracks, edges, moisture)."""
    tags = [LABELS['body_color'][f['body_color']]]
    if f['coating_color'] == 'none' or f['coating_thickness'] == 'none':
        tags.append('Little to no coating')
    else:
        thick = {'thin': 'Thin', 'thick': 'Thick', 'patchy': 'Patchy'}[f['coating_thickness']]
        color = {'white': 'White', 'yellow': 'Yellow', 'grey': 'Grey', 'brown_black': 'Dark'}[f['coating_color']]
        tags.append('%s %s Coating' % (thick, color))
    if f['swelling'] != 'none':
        tags.append('Puffy shape' if f['swelling'] == 'noticeable' else 'Slightly puffy')
    if f['thin_body']:
        tags.append('Thin shape')
    if f['tooth_marks'] != 'none':
        tags.append('Tooth-mark edges')
    if f['cracks'] != 'none':
        tags.append('Surface cracks' if f['cracks'] == 'many' else 'A few cracks')
    if f['red_dots']:
        tags.append('Red dots')
    if f['tip_red']:
        tags.append('Red tip')
    if f['moisture'] != 'normal':
        tags.append('Dry surface' if f['moisture'] == 'dry' else 'Very moist')

    color_txt = {
        'pink': 'Light pink to light red, the most common everyday look.',
        'pale': 'Lighter than the typical pink.',
        'red': 'Redder than the typical light pink.',
        'dark_red': 'A deep red tone.',
        'purplish': 'A purplish or bluish tint.',
    }[f['body_color']]
    if f['tip_red']:
        color_txt += ' The tip looks redder than the rest.'
    coat_txt = {
        'thin': 'A thin coating you can see the tongue through, which is typical.',
        'none': 'Very little coating, so the surface looks bare or shiny.',
        'thick': 'A thicker coating that hides more of the surface.',
        'patchy': 'An uneven coating with smoother, map-like patches.',
    }[f['coating_thickness']]
    if f['coating_color'] not in ('white', 'none'):
        coat_txt += ' It has a %s tint.' % {'yellow': 'yellow', 'grey': 'grey', 'brown_black': 'dark'}[f['coating_color']]
    shape_txt = {'none': 'Even shape with no obvious puffiness.', 'mild': 'Slightly puffy or wide.',
                 'noticeable': 'Looks puffy and wide.'}[f['swelling']]
    if f['thin_body']:
        shape_txt = 'Looks thinner or narrower than average.'
    rows = [
        {'label': 'Color', 'value': color_txt},
        {'label': 'Coating', 'value': coat_txt},
        {'label': 'Shape', 'value': shape_txt},
        {'label': 'Cracks', 'value': {'none': 'No noticeable cracks.', 'few': 'A few small lines or a center groove.',
                                      'many': 'Several cracks or grooves across the surface.'}[f['cracks']]},
        {'label': 'Edges', 'value': {'none': 'Smooth edges.', 'mild': 'Light wavy marks along the sides.',
                                     'noticeable': 'Clear scalloped tooth marks along the sides.'}[f['tooth_marks']]},
        {'label': 'Moisture', 'value': {'normal': 'Normal moisture.', 'dry': 'Looks on the dry side.',
                                        'wet': 'Looks very moist or glossy.'}[f['moisture']]},
    ]
    if f['red_dots']:
        rows.append({'label': 'Surface', 'value': 'Small raised red dots are visible.'})
    return tags, rows


def suggestions(f):
    out = []
    add = lambda title, text: out.append({'title': title, 'text': text})
    if f['moisture'] == 'dry' or f['cracks'] != 'none' or f['body_color'] in ('red', 'dark_red'):
        add('Hydration', 'Sip water through the day, aiming for pale-yellow urine. Cut back on late-day caffeine '
            'and alcohol, which can leave the mouth dry.')
    if f['coating_thickness'] in ('thick', 'patchy') or f['coating_color'] in ('yellow', 'grey', 'brown_black'):
        add('Oral hygiene', 'Brush twice a day and gently clean your tongue from back to front with a scraper or '
            'soft brush each morning. Coffee, tea, tobacco, and some candies can tint the coating.')
    if f['coating_thickness'] == 'thick' or f['coating_color'] == 'yellow' or f['swelling'] != 'none':
        add('Food', 'Lean on whole foods: vegetables, fruit, beans, and simple proteins. Go easy on fried food, '
            'sugar, and heavy late-night meals for a week or two and see how your tongue looks.')
    if f['tooth_marks'] != 'none' or f['swelling'] != 'none' or f['body_color'] == 'pale':
        add('Energy and rest', 'Aim for 7 to 9 hours of steady sleep and regular meals. Gentle daily movement '
            'like a 20-minute walk helps many people feel steadier.')
    if f['body_color'] in ('red', 'dark_red') or f['tip_red'] or f['red_dots']:
        add('Stress and spice', 'Notice whether stress, short sleep, or very spicy or hot foods line up with redder '
            'days. A calm wind-down before bed can help.')
    if f['body_color'] == 'pale' or f['thin_body']:
        add('Nourishment', 'Include iron and protein foods such as leafy greens, beans, eggs, fish, or meat, and '
            'eat regular meals. Ask your doctor about a simple blood test if you often feel tired.')
    if f['body_color'] == 'purplish':
        add('Circulation', 'Regular movement, stretching, and staying warm support healthy circulation. If the '
            'tint stays or comes with other changes, check in with your doctor.')
    if not out:
        add('Keep it up', 'Your tongue shows a typical, balanced look. Keep up water, whole foods, good sleep, '
            'and daily brushing.')
    add('Track it', 'Scan in the morning before eating or brushing, in the same light, every week or two. '
        'Trends tell you more than a single photo.')
    return out[:5]


def build_report(raw):
    f = normalize_features(raw)
    dims, overall = score_features(f)
    tags, rows = observations(f)
    summary = str((raw or {}).get('summary') or '').strip()
    if re.search(r'(?i)\b(ai|artificial intelligence|grok|model|algorithm|diagnos\w*|deficien\w*|disease)\b', summary):
        summary = ''
    summary = summary[:320]
    report = {
        'ok': True, 'features': f, 'dimensions': dims, 'overall': overall, 'band': _band(overall),
        'tags': tags, 'details': rows, 'suggestions': suggestions(f), 'summary': summary,
        'observations_note': OBS_NOTE, 'disclaimer': DISCLAIMER,
        'quality_note': str((raw or {}).get('quality_note') or '')[:160],
    }
    if f['spot_of_concern']:
        report['care_note'] = ('We noticed an area that looks different from the rest of the tongue. A photo can\'t '
                               'tell what it is. If you have a sore, patch, or lump that lasts more than two weeks, '
                               'please have a dentist or doctor take a look.')
    return report


def analyze_tongue(image_b64, mime='image/jpeg'):
    raw = _vision(image_b64, mime or 'image/jpeg')
    if not raw:
        return {'ok': False, 'error': 'We could not read that photo right now. Please try again in a minute.'}
    if not _bool(raw.get('is_tongue', False)):
        return {'ok': False, 'not_tongue': True,
                'error': "We couldn't find a tongue in that photo. Stick your tongue all the way out, face a window, "
                         'and fill the frame with your tongue.'}
    if str(raw.get('quality') or '').lower() == 'poor':
        return {'ok': False, 'retake': True,
                'error': 'That photo is too dark or blurry to read. Try daylight from a window, hold the phone '
                         'steady about 6 inches away, and turn off filters.'}
    return build_report(raw)


# ---------------- history (logged-in only) ----------------

def _safe_email(email):
    return re.sub(r'[^a-z0-9._+-]+', '_', (email or 'anon').strip().lower())[:80]


def _path(email):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    return os.path.join(HISTORY_DIR, _safe_email(email) + '.json')


def load_history(email):
    path = _path(email)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write(email, rows):
    with open(_path(email), 'w', encoding='utf-8') as fh:
        json.dump(rows[:200], fh)


def save_scan(email, report, thumb=''):
    now = central_now()
    thumb = thumb if (isinstance(thumb, str) and thumb.startswith('data:image/') and len(thumb) < 60000) else ''
    entry = {
        'id': now.strftime('%Y%m%d%H%M%S%f'),
        'scanned_at': now.strftime('%Y-%m-%d %H:%M ') + (now.tzname() or 'CT'),
        'overall': report.get('overall'), 'band': report.get('band'),
        'dimensions': report.get('dimensions'), 'tags': report.get('tags'),
        'features': report.get('features'), 'thumb': thumb,
    }
    rows = load_history(email)
    rows.insert(0, entry)
    _write(email, rows)
    return entry


def delete_scan(email, scan_id):
    rows = load_history(email)
    kept = [r for r in rows if str(r.get('id')) != str(scan_id)]
    if len(kept) == len(rows):
        return False
    _write(email, kept)
    return True


def delete_history(email):
    path = os.path.join(HISTORY_DIR, _safe_email(email) + '.json')
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


# ---------------- routes ----------------

_RATE = {}


def _rate_ok(key, limit=15, window=3600):
    now = time.time()
    hits = [t for t in _RATE.get(key, []) if now - t < window]
    if len(hits) >= limit:
        _RATE[key] = hits
        return False
    hits.append(now)
    _RATE[key] = hits
    if len(_RATE) > 5000:
        _RATE.clear()
    return True


def register_tongue_scan_routes(app):
    from flask import render_template, request, session, jsonify

    def _email():
        return (session.get('email') or session.get('user_email') or '').strip().lower()

    def _logged_in():
        return bool(session.get('user_id') and _email())

    def page():
        return render_template('tongue_scanner.html', logged_in=_logged_in(), disclaimer=DISCLAIMER)

    def _read_image():
        data = request.get_json(silent=True) or {}
        b64 = data.get('image_b64') or ''
        mime = data.get('mime') or 'image/jpeg'
        if not b64 and request.files.get('file'):
            import base64
            f = request.files['file']
            b64 = base64.b64encode(f.read()).decode('ascii')
            mime = f.mimetype or mime
        b64 = ''.join(str(b64).split())
        if b64.lower().startswith('data:') and ',' in b64:
            head, b64 = b64.split(',', 1)
            m = re.match(r'data:([^;]+)', head, re.I)
            if m:
                mime = m.group(1)
        if mime.lower() not in ('image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/heic', 'image/heif'):
            return None, mime, data, 'Please use a JPEG or PNG photo.'
        if len(b64) < 200:
            return None, mime, data, 'Choose or take a photo of your tongue first.'
        if len(b64) > 9000000:
            return None, mime, data, 'That photo is too large. Try a smaller photo.'
        if not re.fullmatch(r'[A-Za-z0-9+/=_-]+', b64):
            return None, mime, data, 'That file does not look like a photo. Please try another one.'
        return b64, mime, data, None

    def api_scan():
        b64, mime, data, err = _read_image()
        if err:
            return jsonify({'ok': False, 'error': err}), 400
        ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or '').split(',')[0].strip()
        if not _rate_ok(_email() or ip, limit=25 if _logged_in() else 12):
            return jsonify({'ok': False, 'error': 'You have scanned a lot this hour. Please try again a little later.'}), 429
        try:
            result = analyze_tongue(b64, mime)
        except Exception as exc:
            print('[TongueScan] analysis failed:', exc)
            result = {'ok': False, 'error': 'We could not read that photo right now. Please try again.'}
        result['logged_in'] = _logged_in()
        result['saved'] = False
        if result.get('ok') and _logged_in() and (data or {}).get('save', True) is not False:
            try:
                entry = save_scan(_email(), result, (data or {}).get('thumb') or '')
                result['saved'] = True
                result['scan_id'] = entry['id']
            except Exception as exc:
                print('[TongueScan] save failed:', exc)
        return jsonify(result)

    def api_history():
        if not _logged_in():
            return jsonify({'ok': True, 'items': [], 'logged_in': False})
        return jsonify({'ok': True, 'items': load_history(_email())[:60], 'logged_in': True})

    def api_history_delete():
        if not _logged_in():
            return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        sid = (request.get_json(silent=True) or {}).get('id') or request.form.get('id')
        return jsonify({'ok': delete_scan(_email(), sid)})

    routes = [
        ('/tongue-scanner', 'tongue_scanner_page', page, ['GET']),
        ('/health-app/tongue-scanner', 'tongue_scanner_page_app', page, ['GET']),
        ('/api/tongue-scan', 'api_tongue_scan', api_scan, ['POST']),
        ('/api/tongue-scan/history', 'api_tongue_scan_history', api_history, ['GET']),
        ('/api/tongue-scan/history/delete', 'api_tongue_scan_history_delete', api_history_delete, ['POST']),
    ]
    existing = {r.rule: r.endpoint for r in app.url_map.iter_rules()}
    for path, endpoint, view, methods in routes:
        if path in existing:
            app.view_functions[existing[path]] = view
            continue
        app.add_url_rule(path, endpoint, view, methods=methods)
    print('[Root Cause] Registered /tongue-scanner + tongue scan APIs')
