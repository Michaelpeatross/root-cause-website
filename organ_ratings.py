"""Plain-language organ ratings from a scan file. No raw coefficients."""
import re
from html import escape

# title, keywords, finding, first step, clinician question
ORGANS = (
    ('Lungs', ('lung', 'pulmon', 'bronch', 'pleura', 'alveol'),
     'Breathing patterns were among the louder signals. This is not a lung test.',
     'Notice indoor air and how stairs feel. Mention ongoing shortness of breath to a clinician.',
     'Shortness of breath or a cough should be checked on its own. Which basic breathing questions belong at a visit, separate from this scan?'),
    ('Kidneys', ('kidney', 'renal', 'nephro'),
     'Kidney patterns were louder than most other organs. This is not a kidney-function test.',
     'Sip water through the day rather than a large amount at night.',
     'Should I have a basic kidney panel (creatinine, eGFR) if I have not had one this year?'),
    ('Brain and nerves', ('brain', 'cerebr', 'nerve', 'nervus', 'pituitary', 'hypothalam'),
     'Brain and nerve patterns were among the stronger signals. This is load, not a diagnosis.',
     'Keep caffeine to the morning and try an earlier bedtime for several nights.',
     'Sleep and mental load seem tied to how I feel. What should I track before any further testing?'),
    ('Lymph', ('lymph',),
     'Drainage patterns were busy on this scan. This is not an infection test.',
     'Walk daily and spread water through the day.',
     'I feel puffy or slow to recover. What symptoms should make me come in, versus walking and drinking more water?'),
    ('Intestines', ('intestin', 'colon', 'bowel', 'duoden', 'ileum', 'rectum'),
     'The intestinal pattern was louder than many other organs. This is not a colonoscopy result.',
     'Simpler meals, chew well, and cut constant snacking for a week.',
     'Meals feel heavy. What symptoms would make a stool test reasonable, versus a simpler-meals trial first?'),
    ('Stomach', ('stomach', 'gastric', 'esophag'),
     'Stomach patterns showed extra signal. This is not an ulcer test.',
     'Smaller meals, and less to drink with the meal if you bloat easily.',
     'If I have burning or reflux, is an H. pylori test worth ordering, separate from this scan?'),
    ('Pancreas', ('pancrea',),
     'Pancreas patterns were part of the louder group. This is not a blood-sugar diagnosis.',
     'Pair carbs with protein and skip sweet drinks for a week.',
     'Is a standard glucose or A1C check due, separate from this wellness scan?'),
    ('Liver', ('liver', 'hepat'),
     'Liver patterns were active. This is not a liver-disease test.',
     'Skip alcohol and late heavy dinners for a week and see how mornings feel.',
     'Which liver labs, if any, match late heavy meals or alcohol, separate from this scan?'),
    ('Heart', ('heart', 'cardiac', 'myocard', 'coronar'),
     'Heart patterns were in the middle of the pack. This is not an EKG or a stress test.',
     'Take a daily walk and keep ultra-processed snacks down this week.',
     'For my age, which basic heart checks are already appropriate, separate from this scan?'),
    ('Adrenals', ('adrenal', 'suprarenal'),
     'Adrenal patterns were quieter than the louder organs. This is not a hormone lab.',
     'An earlier bedtime beats extra caffeine.',
     'Sleep and caffeine seem to drive my energy. What should I track before hormone testing?'),
    ('Thyroid', ('thyroid', 'thyreoid', 'parathyroid'),
     'Thyroid patterns were quieter on this scan. This is not a thyroid blood test.',
     'Ask your clinician whether a standard thyroid panel is due.',
     'Is a standard thyroid panel due, separate from this wellness scan?'),
    ('Skin', (' skin', 'dermal', 'epiderm', 'cutis'),
     'Skin patterns were quieter than the louder organs. This is not a skin diagnosis.',
     'Keep showers shorter and notice whether sugar-heavy days line up with flare-ups.',
     'If I have a rash or a spot that is changing, that needs a look in person. What else is worth mentioning?'),
    ('Gallbladder', ('gallbladder', 'gall bladder', 'bile', 'biliar', 'cholecyst'),
     'Gallbladder patterns were among the quieter organs on this scan. This is not a gallbladder test.',
     'Smaller meals, and go easy on fried food while you watch how you feel.',
     'Fatty meals sit heavy. Is a standard liver panel worth ordering, separate from this scan?'),
)


def _values_for(lines, keys):
    vals = []
    for line in lines:
        low = ' ' + line.lower()
        if not any(k in low for k in keys):
            continue
        match = re.search(r'D\s*=\s*(\d+(?:\.\d+)?)', line)
        if not match:
            continue
        value = float(match.group(1))
        if value <= 1:
            value *= 100
        if 0 <= value <= 100:
            vals.append(value)
    return vals


def _scan_lines(raw_data):
    lines = []
    for raw in (raw_data or '').splitlines():
        line = raw.strip()
        if len(line) < 4:
            continue
        if re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', line) and re.search(r'\b\d{3,5}\b', line):
            continue
        lines.append(line)
    return lines


def rate_organs(raw_data, calendar_age=None, biometric_age=None):
    """Return every major organ, loudest first. Ratings only, no machine numbers."""
    lines = _scan_lines(raw_data)
    measured = []
    for title, keys, why, step, question in ORGANS:
        vals = _values_for(lines, keys)
        if len(vals) < 3:
            measured.append((None, title, why, step, question))
            continue
        top = sorted(vals, reverse=True)[:12]
        measured.append((sum(top) / len(top), title, why, step, question))
    known = [row[0] for row in measured if row[0] is not None]
    if not known:
        return []
    lo, hi = min(known), max(known)
    span = hi - lo or 1
    if calendar_age and biometric_age:
        from biometric_age import cap_to_calendar
        biometric_age = cap_to_calendar(calendar_age, biometric_age)
        year_span = max(0, int(biometric_age) - int(calendar_age))
    elif calendar_age:
        year_span = 5
    else:
        year_span = 5
    rows = []
    for avg, title, why, step, question in measured:
        if avg is None:
            rating, band, organ_age = 84, 'Steady', calendar_age
        else:
            ratio = (avg - lo) / span
            rating = int(round(86 - ratio * 38))
            rating = max(42, min(92, rating))
            if calendar_age:
                organ_age = int(calendar_age) + int(round(ratio * year_span))
                organ_age = min(organ_age, int(calendar_age) + 5)
            else:
                organ_age = None
            if rating >= 78:
                band = 'Steady'
            elif rating >= 66:
                band = 'Mild load'
            elif rating >= 54:
                band = 'Moderate load'
            else:
                band = 'Higher load'
        rows.append({
            'title': title,
            'rating': rating,
            'band': band,
            'organ_age': organ_age,
            'signal': avg,
            'why': why,
            'step': step,
            'question': question,
        })
    rows.sort(key=lambda row: (row['rating'], row['title']))
    return rows


def priority_items(raw_data, limit=3, calendar_age=None, biometric_age=None):
    rows = rate_organs(raw_data, calendar_age=calendar_age, biometric_age=biometric_age)
    loud = [row for row in rows if row['band'] != 'Steady'] or rows
    return [(row['title'], row['why'], row['step']) for row in loud[:limit]]


def organ_signals(raw_data):
    """Comparable loudness per organ. Higher means more load. Not shown to the client."""
    lines = _scan_lines(raw_data)
    found = {}
    for title, keys, _why, _step, _question in ORGANS:
        vals = _values_for(lines, keys)
        if len(vals) < 3:
            continue
        top = sorted(vals, reverse=True)[:12]
        found[title] = sum(top) / len(top)
    return found


def _bar_color(band):
    return {
        'Higher load': '#c2413a',
        'Moderate load': '#d97706',
        'Mild load': '#0f766e',
        'Steady': '#1f8a5b',
    }.get(band, '#64748b')


def _bar_class(band):
    return {
        'Higher load': 'bar-high',
        'Moderate load': 'bar-mod',
        'Mild load': 'bar-mild',
        'Steady': 'bar-ok',
    }.get(band, 'bar-mod')


def _rating_bar(rating, band):
    width = max(8, min(100, int(rating)))
    color = _bar_color(band)
    return (
        '<table class="rating-bar" width="100%%" cellpadding="0" cellspacing="0"><tr>'
        '<td width="%s%%" class="%s" bgcolor="%s">%s</td>'
        '<td class="bar-rest" bgcolor="#e7f0ec">&nbsp;</td>'
        '</tr></table>'
    ) % (width, _bar_class(band), color, rating)


def _change_class(label):
    if label.startswith('Improved') or label.startswith('Quieter'):
        return 'chg-better'
    if label.startswith('Louder'):
        return 'chg-worse'
    return 'chg-same'


def _change_label(delta, band):
    still = band in ('Higher load', 'Moderate load')
    if delta is None:
        return 'No earlier scan' if not still else 'Still work to do'
    if delta <= -1.5:
        return 'Quieter, still work to do' if still else 'Improved'
    if delta >= 1.5:
        return 'Louder — needs work'
    if still:
        return 'About the same — still work to do'
    return 'About the same'


def organ_board_html(raw_data, calendar_age=None, biometric_age=None, client_name='Client', previous_scans=None):
    rows = rate_organs(raw_data, calendar_age=calendar_age, biometric_age=biometric_age)
    if not rows:
        return ''
    first = escape(((client_name or 'Client').split() or ['there'])[0])
    priors = [scan for scan in (previous_scans or []) if scan.get('signals')]
    prior = priors[-1] if priors else None
    prior_signals = (prior or {}).get('signals') or {}
    prior_label = (prior or {}).get('label') or 'your last scan'
    age_note = ''
    if calendar_age:
        age_note = ' Calendar age on this scan is %s.' % int(calendar_age)
    history = ''
    if priors:
        labels = []
        for scan in priors:
            label = scan.get('label') or 'Earlier scan'
            if label not in labels:
                labels.append(label)
        history = (
            '<p class="rec-note">Earlier scans for reference: ' + escape(', '.join(labels))
            + '. The change column compares this scan with ' + escape(prior_label)
            + '. Quieter means that organ improved. Louder, or still in a higher load, is work still to do.</p>'
        )
    head = (
        '<h3>Major organs</h3>'
        '<p>' + first + ', every major organ is listed below, loudest first. '
        'A longer green bar is quieter. A short red bar is louder and still needs work. '
        'The age is a bioenergetic estimate beside calendar age, not a clinical organ test and not a diagnosis.'
        + age_note + '</p>'
        + history
    )
    improved, needs = [], []
    chart = []
    body = []
    change_head = '<th>Since ' + escape(prior_label) + '</th>' if prior else ''
    for row in rows:
        age = str(row['organ_age']) if row['organ_age'] else '—'
        change_cell = ''
        if prior:
            old = prior_signals.get(row['title'])
            new = row.get('signal')
            delta = None if old is None or new is None else new - old
            label = _change_label(delta, row['band'])
            change_cell = '<td class="' + _change_class(label) + '">' + escape(label) + '</td>'
            if label.startswith('Improved') or label.startswith('Quieter'):
                improved.append(row['title'])
            if 'work' in label.lower() or label.startswith('Louder'):
                needs.append(row['title'])
        chart.append(
            '<tr><td class="chart-name"><strong>' + escape(row['title']) + '</strong></td>'
            '<td class="chart-bar">' + _rating_bar(row['rating'], row['band']) + '</td>'
            '<td class="chart-age">' + age + '</td></tr>'
        )
        body.append(
            '<tr><td><strong>' + escape(row['title']) + '</strong></td>'
            '<td class="' + _bar_class(row['band']) + '">' + str(row['rating']) + ' · ' + escape(row['band']) + '</td>'
            '<td>' + age + '</td>'
            + change_cell
            + '<td>' + escape(row['why']) + '</td></tr>'
        )
    summary = ''
    if prior:
        improved_line = ', '.join(improved) if improved else 'None this time'
        needs_line = ', '.join(needs) if needs else 'None standing out'
        summary = (
            '<p><strong>Improved since ' + escape(prior_label) + ':</strong> ' + escape(improved_line) + '</p>'
            '<p><strong>Still work to do:</strong> ' + escape(needs_line) + '</p>'
        )
    return (
        head
        + '<p class="chart-key"><span class="swatch bar-high">Louder</span> '
        '<span class="swatch bar-mod">Moderate</span> '
        '<span class="swatch bar-mild">Mild</span> '
        '<span class="swatch bar-ok">Quieter</span></p>'
        + '<table class="organ-chart" width="100%"><thead><tr><th>Organ</th><th>Rating bar</th><th>Age</th></tr></thead><tbody>'
        + ''.join(chart)
        + '</tbody></table>'
        + '<table class="organ-board"><thead><tr><th>Organ</th><th>Rating</th><th>Age</th>'
        + change_head
        + '<th>What stood out</th></tr></thead><tbody>'
        + ''.join(body)
        + '</tbody></table>'
        + summary
        + '<p class="rec-note">Higher rating means quieter on this scan. Organ age is not a lab result.</p>'
    )


# Everyday names only. Obscure scanner metals stay off the client page.
_TOXIN_NAMES = (
    ('Aluminum', ('aluminium', 'aluminum')),
    ('Nickel', ('nickel',)),
    ('Mercury', ('mercury',)),
    ('Lead', ('lead',)),
    ('Benzene', ('benzene',)),
    ('Pesticides', ('pesticide', 'hexachlorobenzene')),
    ('Cadmium', ('cadmium',)),
    ('Arsenic', ('arsenic',)),
    ('Formaldehyde', ('formaldehyde',)),
)


def named_toxins(raw_data, limit=6):
    """Loudest recognizable toxin names. No machine numbers."""
    best = {}
    for line in _scan_lines(raw_data):
        match = re.search(r'D=([0-9.]+)', line)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        low = line.lower()
        for title, keys in _TOXIN_NAMES:
            if any(re.search(r'\b' + re.escape(key), low) for key in keys):
                best[title] = max(best.get(title, 0), value)
    ranked = sorted(best, key=lambda name: (-best[name], name))
    return ranked[:limit]


def toxin_board_html(raw_data, client_name='Client'):
    names = named_toxins(raw_data)
    if not names:
        return ''
    first = escape(((client_name or 'Client').split() or ['there'])[0])
    chips = ''.join(
        '<td class="toxin-chip" bgcolor="#7c2d12">' + escape(name) + '</td>'
        for name in names
    )
    return (
        '<h3>Toxins that stood out</h3>'
        '<p>' + first + ', these everyday toxin patterns were louder than the other toxin names on this scan. '
        'This is not a blood test, a hair-metal test, or a diagnosis.</p>'
        '<table class="toxin-row" cellpadding="4" cellspacing="4"><tr>' + chips + '</tr></table>'
    )


_FOOD_TAG = re.compile(
    r'^(?P<name>.+?)(?:,\s*|\s+)(?P<tag>food|dairy|fruits?|vegetables?|cereals?|meats?|drinks?|spices?|fish|seeds?|oils?)\s*$',
    re.I,
)
_FOOD_SKIP = re.compile(
    r'rbc|coral|nona|shampoo|nectar|vita|cleanse|fulfil|enteropath|blood sugar|'
    r'cornea|salmonella|glucose|methyl|chem\b|rattle|sterlet|turtle|beluga|huso|allergen',
    re.I,
)
_FOOD_ALIAS = {
    'glair': 'Egg white',
    'yolk': 'Egg yolk',
    'chicken egg yolk': 'Egg yolk',
    'oatmeal': 'Oatmeal',
    'cow milk': 'Cow milk',
    'red capsicum': 'Red pepper',
    'colombian coffee': 'Coffee',
    'sunflower': 'Sunflower seeds',
    'condensed milk': 'Condensed milk',
    'goat cheese': 'Goat cheese',
}


def _food_label(raw_name):
    chunk = re.sub(r'\s+', ' ', raw_name or '').strip(' ,')
    chunk = re.split(r'E=\d+', chunk)[-1].strip(' ,')
    match = _FOOD_TAG.match(chunk)
    if not match:
        return None
    if _FOOD_SKIP.search(chunk):
        return None
    label = match.group('name').strip(' ,')
    if len(label) < 3 or len(label.split()) == 1 and len(label) < 3:
        return None
    if re.match(r'^[A-Za-z]\s', label):
        return None
    key = label.lower()
    if key in ('food', 'dairy', 'drinks', 'meat', 'fish', 's milk'):
        return None
    if '[' in label or ']' in label:
        return None
    if re.search(r'absinth|schnapps|grappa|tequila|\bgin\b|\bjin\b|\bport\b|vodka|whisky|whiskey|\brum\b|brandy|cognac|vermouth|liqueur|buffalo|ostrich|\bgoose\b|\bveal\b', key):
        return None
    if key in _FOOD_ALIAS:
        return _FOOD_ALIAS[key]
    return ' '.join(word.capitalize() for word in key.replace("'", "'").split())


def _food_scores(raw_data):
    best = {}
    for line in _scan_lines(raw_data):
        parts = re.split(r'\s+D=([0-9.]+)', line)
        for name, raw_value in zip(parts[0::2], parts[1::2]):
            try:
                value = float(raw_value)
            except ValueError:
                continue
            label = _food_label(name)
            if not label:
                continue
            best[label] = max(best.get(label, 0), value)
    return best


def named_foods(raw_data, limit=8):
    """Loudest everyday foods. No machine numbers and no allergy diagnosis."""
    best = _food_scores(raw_data)
    ranked = sorted(best, key=lambda name: (-best[name], name))
    return ranked[:limit]


# Practical foods we will suggest only when the scan read them quieter than the sensitivities.
_EAT_LABELS = {
    'Cucumbers': 'Cucumber',
    'Cherry': 'Cherry',
    'Cranberry': 'Cranberry',
    'Pumpkin Seeds': 'Pumpkin seeds',
    'Asparagus': 'Asparagus',
    'Natural Rice': 'Rice',
    'Rice': 'Rice',
    'Pear': 'Pear',
    'Pumpkin': 'Pumpkin',
    'Hazelnut': 'Hazelnut',
    'Beet': 'Beet',
    'Red Lentil': 'Red lentils',
    'Green Tea': 'Green tea',
    'Sardines': 'Sardines',
    'Mackerel': 'Mackerel',
    'Walnuts': 'Walnuts',
    'Potato': 'Potato',
    'Celery': 'Celery',
    'Green Peas': 'Green peas',
    'Apricot': 'Apricot',
    'Herring': 'Herring',
}
_MEAL_ROLES = (
    ('fruit', ('Pear', 'Cherry', 'Cranberry', 'Apricot')),
    ('nuts', ('Walnuts', 'Hazelnut', 'Pumpkin seeds')),
    ('drink', ('Green tea',)),
    ('grain', ('Rice', 'Potato')),
    ('fish', ('Sardines', 'Mackerel', 'Herring')),
    ('veg', ('Cucumber', 'Asparagus', 'Pumpkin', 'Beet', 'Celery', 'Green peas', 'Potato')),
    ('legume', ('Red lentils', 'Green peas')),
)


def foods_to_eat(raw_data, avoid=None, limit=8):
    """Quieter everyday foods. Skips the foods that already stood out."""
    scores = _food_scores(raw_data)
    avoid = set(avoid or [])
    loud = [scores[name] for name in avoid if name in scores]
    floor = min(loud) if loud else 0.2
    best = {}
    for label, score in scores.items():
        shown = _EAT_LABELS.get(label)
        if not shown or shown in avoid or score >= floor:
            continue
        best[shown] = min(best.get(shown, score), score)
    roles = dict(_MEAL_ROLES)
    chosen = []
    used = set()
    for role in ('veg', 'veg', 'veg', 'grain', 'fruit', 'fish', 'legume', 'drink', 'nuts'):
        options = [name for name in roles[role] if name in best and name not in used]
        if not options:
            continue
        pick = options[0]
        chosen.append(pick)
        used.add(pick)
        if len(chosen) >= limit:
            return chosen
    rest = sorted((name for name in best if name not in used), key=lambda name: (best[name], name))
    for name in rest:
        chosen.append(name)
        if len(chosen) >= limit:
            break
    return chosen


def meal_ideas(foods):
    """A few plain meals built only from the quieter foods."""
    order = list(foods or [])
    have = set(order)
    used = set()
    roles = dict(_MEAL_ROLES)

    def take(role):
        options = [name for name in roles[role] if name in have and name not in used]
        if not options:
            return None
        pick = min(options, key=lambda name: order.index(name))
        used.add(pick)
        return pick

    vegs = [name for name in (take('veg'), take('veg'), take('veg')) if name]
    grain = take('grain')
    fruit = take('fruit')
    fish = take('fish')
    legume = take('legume')
    drink = take('drink')
    nuts = take('nuts')
    meals = []

    breakfast = None
    if grain and fruit and nuts:
        breakfast = '%s with %s and %s' % (grain, fruit.lower(), nuts.lower())
    elif grain and fruit:
        breakfast = '%s with %s' % (grain, fruit.lower())
    elif fruit and nuts:
        breakfast = '%s and %s' % (fruit, nuts.lower())
    elif grain:
        breakfast = grain
    elif fruit:
        breakfast = fruit
    if breakfast and drink:
        breakfast += ', and a cup of ' + drink.lower()
    elif drink:
        breakfast = 'A cup of ' + drink.lower()
    if breakfast:
        meals.append(('Breakfast', breakfast + '.'))

    lunch_bits = []
    if fish and vegs:
        lunch_bits = [fish, 'with ' + vegs[0].lower()]
        if grain:
            lunch_bits.append('and ' + grain.lower())
    elif fish and grain:
        lunch_bits = [fish, 'with ' + grain.lower()]
    elif vegs and grain:
        lunch_bits = [vegs[0], 'with ' + grain.lower()]
    if lunch_bits:
        meals.append(('Lunch', ' '.join(lunch_bits) + '.'))

    sides = vegs[1:3]
    if legume and len(sides) >= 2:
        dinner = '%s with %s and %s.' % (legume, sides[0].lower(), sides[1].lower())
    elif legume and sides:
        dinner = '%s with %s.' % (legume, sides[0].lower())
    elif legume:
        dinner = legume + '.'
    elif len(sides) >= 2:
        dinner = '%s and %s.' % (sides[0], sides[1].lower())
    else:
        dinner = None
    if dinner:
        meals.append(('Dinner', dinner))
    return meals[:3]


def food_board_html(raw_data, client_name='Client'):
    names = named_foods(raw_data)
    if not names:
        return ''
    first = escape(((client_name or 'Client').split() or ['there'])[0])
    cells = [
        '<td class="food-chip" bgcolor="#166534">' + escape(name) + '</td>'
        for name in names
    ]
    rows = ''.join(
        '<tr>' + ''.join(cells[i:i + 4]) + '</tr>'
        for i in range(0, len(cells), 4)
    )
    return (
        '<h3>Food sensitivities</h3>'
        '<p>' + first + ', these foods stood out more than the other foods on this scan. '
        'This is a scan pattern, not an allergy test, not an intolerance test, and not a diagnosis.</p>'
        '<table class="food-row" cellpadding="4" cellspacing="4">' + rows + '</table>'
        + _eat_board_html(raw_data, names, first)
    )


def _chip_table(names, css, color):
    cells = [
        '<td class="%s" bgcolor="%s">%s</td>' % (css, color, escape(name))
        for name in names
    ]
    return ''.join(
        '<tr>' + ''.join(cells[i:i + 4]) + '</tr>'
        for i in range(0, len(cells), 4)
    )


def _eat_board_html(raw_data, avoid, first):
    foods = foods_to_eat(raw_data, avoid=avoid)
    if not foods:
        return ''
    meals = meal_ideas(foods)
    meal_html = ''.join(
        '<li><strong>%s.</strong> %s</li>' % (escape(title), escape(text))
        for title, text in meals
    )
    return (
        '<h3>Foods to lean on</h3>'
        '<p>' + first + ', these foods were quieter than the ones that stood out. '
        'Start here. This is not a diet prescription.</p>'
        '<table class="eat-row" cellpadding="4" cellspacing="4">'
        + _chip_table(foods, 'eat-chip', '#1e40af')
        + '</table>'
        + ('<h3>Meal ideas</h3><ul class="meal-list">' + meal_html + '</ul>' if meal_html else '')
        + '<p class="rec-note">Leave off the foods that stood out while you try these. '
        'This is not a meal plan from a dietitian.</p>'
    )
