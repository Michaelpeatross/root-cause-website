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

def save_meal(email, meal):
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
    entry = _clean_row(entry)
    key = _meal_key(entry)
    rows = [row for row in rows if _meal_key(row) != key]
    rows.insert(0, entry)
    _write(email, rows)
    return entry

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
