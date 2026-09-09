"""Meal photo diary and daily macro totals."""
import json, os, re
from datetime import datetime, timedelta

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

def load_meals(email):
    path = _path(email)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_meal(email, meal):
    rows = load_meals(email)
    entry = {
        'id': datetime.utcnow().strftime('%Y%m%d%H%M%S%f'),
        'eaten_at': meal.get('eaten_at') or datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
        'day': (meal.get('eaten_at') or datetime.utcnow().strftime('%Y-%m-%d'))[:10],
        'name': meal.get('name') or 'Meal photo',
        'portion': meal.get('portion') or '',
        'calories': meal.get('calories'),
        'protein': meal.get('protein'),
        'carbs': meal.get('carbs'),
        'fat': meal.get('fat'),
        'sugar': meal.get('sugar'),
        'fiber': meal.get('fiber'),
        'score': meal.get('score'),
        'label': meal.get('label') or '',
        'notes': meal.get('notes') or '',
    }
    rows.insert(0, entry)
    with open(_path(email), 'w', encoding='utf-8') as fh:
        json.dump(rows[:500], fh)
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
    today = datetime.utcnow().strftime('%Y-%m-%d')
    today_row = next((r for r in out if r['day'] == today), {'day': today, 'meals': 0, 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'sugar': 0, 'avg_score': None})
    return {'today': today_row, 'days': out, 'meals': rows[:80]}
