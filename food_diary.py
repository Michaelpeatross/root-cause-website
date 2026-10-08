"""Meal photo diary and daily macro totals."""
import json, os, re
from datetime import datetime
try:
    from central_time import central_now
except Exception:  # pragma: no cover
    central_now = datetime.now

try:
    from persistent_storage import setup_persistent_paths
    _PATHS = setup_persistent_paths(os.path.dirname(os.path.abspath(__file__)))
    DIARY_DIR = os.path.join(_PATHS.get('data_dir') or os.path.dirname(os.path.abspath(__file__)), 'food_diary')
except Exception:
    DIARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'food_diary')

def _safe(email):
    return re.sub(r'[^a-z0-9._+-]+', '_', (email or 'anon').strip().lower())[:80]

def _path(email):
    os.makedirs(DIARY_DIR, exist_ok=True)
    return os.path.join(DIARY_DIR, _safe(email) + '.json')

def _round(val, digits=1):
    try:
        n = float(val)
    except (TypeError, ValueError):
        return val
    if digits == 0 or abs(n - round(n)) < 0.05:
        return int(round(n))
    return round(n, digits)

def _meal_key(row):
    name = re.sub(r'[^a-z0-9]+', ' ', str((row or {}).get('name') or '').lower()).strip()
    when = str((row or {}).get('eaten_at') or (row or {}).get('day') or '')[:16]
    return name + '|' + when

def _clean_row(row):
    row = dict(row or {})
    for field in ('calories', 'protein', 'carbs', 'fat', 'sugar', 'fiber', 'sodium', 'score'):
        if row.get(field) is not None:
            row[field] = _round(row.get(field), 0 if field in ('calories', 'score') else 1)
    return row

def dedupe_meals(rows):
    seen = set()
    kept = []
    for row in rows or []:
        key = _meal_key(row)
        if not key.strip('|') or key in seen:
            continue
        seen.add(key)
        kept.append(_clean_row(row))
    return kept

def _write(email, rows):
    with open(_path(email), 'w', encoding='utf-8') as fh:
        json.dump(rows[:500], fh)

def load_meals(email):
    path = _path(email)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        rows = data if isinstance(data, list) else []
    except Exception:
        return []
    cleaned = dedupe_meals(rows)
    if cleaned != rows:
        _write(email, cleaned)
    return cleaned

EXTRA_FIELDS = ('save_id', 'photo_key', 'items', 'meal_split', 'source')
EDITABLE = ('name', 'calories', 'protein', 'carbs', 'fat', 'sugar', 'fiber', 'score', 'label', 'notes', 'portion')


def _find_existing(rows, meal):
    """Index of an earlier save of the same meal (same save_id, or same photo the same day)."""
    save_id = str(meal.get('save_id') or '')
    photo_key = str(meal.get('photo_key') or '')
    today = central_now().strftime('%Y-%m-%d')
    for idx, row in enumerate(rows):
        if save_id and str(row.get('save_id') or '') == save_id:
            return idx
        if photo_key and str(row.get('photo_key') or '') == photo_key and (row.get('day') or '') == today:
            return idx
    return -1


def save_meal(email, meal):
    """Add a meal. A repeat save of the same meal (same save_id or same photo today)
    updates the earlier entry instead of adding a duplicate; entry['replaced'] says which."""
    rows = load_meals(email)
    thumb = meal.get('thumbnail') or ''
    if not (str(thumb).startswith('http://') or str(thumb).startswith('https://')):
        thumb = ''
    now = central_now()  # site convention: America/Chicago, so "today" matches the user's day
    entry = {
        'id': now.strftime('%Y%m%d%H%M%S%f'),
        'eaten_at': meal.get('eaten_at') or now.strftime('%Y-%m-%d %H:%M ') + (now.tzname() or 'CT'),
        'day': (meal.get('eaten_at') or now.strftime('%Y-%m-%d'))[:10],
        'name': meal.get('name') or 'Meal photo',
        'portion': meal.get('portion') or '',
        'calories': meal.get('calories'),
        'protein': meal.get('protein'),
        'carbs': meal.get('carbs'),
        'fat': meal.get('fat'),
        'sugar': meal.get('sugar'),
        'fiber': meal.get('fiber'),
        'sodium': meal.get('sodium'),
        'score': meal.get('score'),
        'label': meal.get('label') or '',
        'notes': meal.get('notes') or '',
        'thumbnail': thumb[:240],
    }
    for field in EXTRA_FIELDS:
        if meal.get(field) not in (None, ''):
            entry[field] = meal.get(field)
    entry = _clean_row(entry)
    replaced = False
    idx = _find_existing(rows, meal)
    if idx >= 0:
        old = rows.pop(idx)
        entry['id'] = old.get('id') or entry['id']
        entry['eaten_at'] = old.get('eaten_at') or entry['eaten_at']
        entry['day'] = old.get('day') or entry['day']
        replaced = True
    key = _meal_key(entry)
    rows = [row for row in rows if _meal_key(row) != key]
    rows.insert(0, entry)
    _write(email, rows)
    out = dict(entry)
    out['replaced'] = replaced
    return out


def get_meal(email, meal_id):
    for row in load_meals(email):
        if str(row.get('id')) == str(meal_id or ''):
            return row
    return None


def delete_meal(email, meal_id):
    rows = load_meals(email)
    kept = [row for row in rows if str(row.get('id')) != str(meal_id or '')]
    if len(kept) == len(rows):
        return False
    _write(email, kept)
    return True


def update_meal(email, meal_id, fields):
    """Edit a logged meal in place (name, macros, or a re-edited item list)."""
    rows = load_meals(email)
    for idx, row in enumerate(rows):
        if str(row.get('id')) != str(meal_id or ''):
            continue
        row = dict(row)
        for field in EDITABLE + ('items', 'meal_split'):
            if field in (fields or {}):
                val = fields[field]
                if field == 'name':
                    val = str(val or '').strip()[:80] or row.get('name') or 'Meal'
                row[field] = val
        rows[idx] = _clean_row(row)
        _write(email, rows)
        return rows[idx]
    return None


def _num(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

def daily_summary(email, days=14):
    rows = load_meals(email)
    by_day = {}
    for row in rows:
        day = row.get('day') or (row.get('eaten_at') or '')[:10]
        if not day:
            continue
        bucket = by_day.setdefault(day, {'day': day, 'meals': 0, 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'sugar': 0, 'scores': []})
        bucket['meals'] += 1
        bucket['calories'] += _num(row.get('calories'))
        bucket['protein'] += _num(row.get('protein'))
        bucket['carbs'] += _num(row.get('carbs'))
        bucket['fat'] += _num(row.get('fat'))
        bucket['sugar'] += _num(row.get('sugar'))
        if row.get('score') is not None:
            bucket['scores'].append(_num(row.get('score')))
    out = []
    for day, bucket in sorted(by_day.items(), reverse=True)[:days]:
        scores = bucket.pop('scores')
        bucket['avg_score'] = int(round(sum(scores) / len(scores))) if scores else None
        for key in ('calories', 'protein', 'carbs', 'fat', 'sugar'):
            bucket[key] = int(round(bucket[key]))
        out.append(bucket)
    today = central_now().strftime('%Y-%m-%d')
    today_row = next((r for r in out if r['day'] == today), {'day': today, 'meals': 0, 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'sugar': 0, 'avg_score': None})
    return {'today': today_row, 'days': out, 'meals': rows[:80]}

def delete_meals(email):
    """Remove the whole nutrition log for this account (used by account deletion)."""
    path = os.path.join(DIARY_DIR, _safe(email) + '.json')
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False
