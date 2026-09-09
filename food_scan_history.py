"""Persist client food-scan results with timestamps."""
import json, os, re
from datetime import datetime
try:
    from persistent_storage import setup_persistent_paths
    _PATHS = setup_persistent_paths(os.path.dirname(os.path.abspath(__file__)))
    HISTORY_DIR = os.path.join(_PATHS.get('data_dir') or os.path.dirname(os.path.abspath(__file__)), 'food_scans')
except Exception:
    HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'food_scans')

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

def save_scan(email, payload):
    product = (payload or {}).get('product') or {}
    rating = (payload or {}).get('rating') or {}
    entry = {
        'id': datetime.utcnow().strftime('%Y%m%d%H%M%S%f'),
        'scanned_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
        'code': product.get('code') or '',
        'name': product.get('name') or 'Unknown product',
        'brands': product.get('brands') or '',
        'image': product.get('image') or '',
        'score': rating.get('score'),
        'label': rating.get('label') or '',
        'color': rating.get('color') or '',
        'nutrition_score': rating.get('nutrition_score'),
        'additive_score': rating.get('additive_score'),
        'personal_score': rating.get('personal_score'),
    }
    rows = load_history(email)
    rows.insert(0, entry)
    with open(_path(email), 'w', encoding='utf-8') as fh:
        json.dump(rows[:400], fh)
    return entry

def sorted_history(email, sort='date_desc'):
    rows = list(load_history(email))
    if sort == 'score_desc':
        rows.sort(key=lambda r: (r.get('score') is None, -(r.get('score') or 0)))
    elif sort == 'score_asc':
        rows.sort(key=lambda r: (r.get('score') is None, r.get('score') or 0))
    elif sort == 'name':
        rows.sort(key=lambda r: (r.get('name') or '').lower())
    else:
        rows.sort(key=lambda r: r.get('scanned_at') or '', reverse=True)
    return rows
