"""Per-client medical bot: profile, procedure timeline, and Grok answers."""
import json
import os
import re
from datetime import datetime
from html import escape

from persistent_storage import setup_persistent_paths


def _bots_dir():
    basedir = os.path.abspath(os.path.dirname(__file__))
    storage = setup_persistent_paths(basedir)
    path = os.path.join(storage['data_dir'], 'client_bots')
    os.makedirs(path, exist_ok=True)
    return path


def _safe_email(email):
    cleaned = re.sub(r'[^a-z0-9._+-]+', '_', (email or '').strip().lower())
    return cleaned[:80] or 'unknown'


def profile_path(email):
    return os.path.join(_bots_dir(), f'{_safe_email(email)}.json')


def default_profile(email, name=''):
    return {
        'email': (email or '').strip().lower(),
        'name': name or '',
        'birth_year': None,
        'insurance_carrier': '',
        'preferred_lab': '',
        'allergies': [],
        'medications': [],
        'procedures': [],
        'goals': '',
        'updated_at': None,
    }


def load_profile(email, name=''):
    path = profile_path(email)
    data = default_profile(email, name)
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                data.update(stored)
        except (OSError, json.JSONDecodeError):
            pass
    return data


def save_profile(email, updates, name=''):
    data = load_profile(email, name)
    for key, value in (updates or {}).items():
        if key in data and key != 'email':
            data[key] = value
    data['email'] = (email or '').strip().lower()
    data['updated_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    with open(profile_path(email), 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)
    return data


def add_procedure(email, title, event_date='', notes='', name=''):
    data = load_profile(email, name)
    title = (title or '').strip()
    if not title:
        return data
    data.setdefault('procedures', [])
    data['procedures'].append({
        'date': (event_date or '').strip()[:12],
        'title': title[:200],
        'notes': (notes or '').strip()[:500],
    })
    data['procedures'] = data['procedures'][-80:]
    return save_profile(email, {'procedures': data['procedures']}, name=name)


def timeline_from_documents(documents):
    events = []
    for doc in documents or []:
        title = (
            getattr(doc, 'grok_label', None)
            or getattr(doc, 'original_name', None)
            or 'Medical document'
        )
        date = getattr(doc, 'grok_date', None) or getattr(doc, 'test_date', None) or ''
        events.append({
            'date': date or 'date unknown',
            'title': title,
            'source': 'upload',
            'notes': getattr(doc, 'original_name', '') or '',
        })
    events.sort(key=lambda item: item.get('date') or '', reverse=True)
    return events


def bot_context(profile, documents, report=None):
    lines = [
        f"Client: {profile.get('name') or profile.get('email')}",
        f"Insurance: {profile.get('insurance_carrier') or 'not given'}",
        f"Preferred draw lab: {profile.get('preferred_lab') or 'not given'}",
        f"Birth year: {profile.get('birth_year') or 'not given'}",
        f"Allergies: {', '.join(profile.get('allergies') or []) or 'none listed'}",
        f"Medications: {', '.join(profile.get('medications') or []) or 'none listed'}",
        f"Goals: {profile.get('goals') or 'not given'}",
    ]
    procedures = profile.get('procedures') or []
    if procedures:
        lines.append('Client-entered procedures:')
        for item in procedures[-20:]:
            lines.append(f"- {item.get('date') or 'undated'}: {item.get('title')}")
    uploads = timeline_from_documents(documents)
    if uploads:
        lines.append('Uploaded records:')
        for item in uploads[:25]:
            lines.append(f"- {item.get('date')}: {item.get('title')}")
    if report is not None:
        title = getattr(report, 'title', '') or ''
        lines.append(f'Latest scan title: {title}')
        ai = getattr(report, 'ai_recommendations', None) or getattr(report, 'original_ai_recommendations', '') or ''
        plain = re.sub(r'<[^>]+>', ' ', ai)
        plain = re.sub(r'\s+', ' ', plain).strip()[:1800]
        if plain:
            lines.append('Latest analysis excerpt:')
            lines.append(plain)
    return '\n'.join(lines)


def answer_with_bot(question, profile, documents, report, client_name='Client'):
    from health_advisor import _grok_chat, get_last_grok_error

    first = (client_name or profile.get('name') or 'Client').split()[0]
    context = bot_context(profile, documents, report)
    prompt = f"""You are {first}'s personal Root Cause medical-needs bot.
You only know what is in the context below. Do not invent procedures, dates, or lab values.
If something is missing, say so and ask them to upload the PDF or add it to their timeline.

Answer in 2-5 short plain-text paragraphs.
Educational only — not a diagnosis and not a medication change.
If they ask where to test, give BOTH paths:
1) insurance / One Medical / in-network Quest or Labcorp when the deductible is met
2) cheapest cash-pay: compare LabRecon, then order Ulta Lab Tests, GoodLabs, or Walk-In Lab. Never hospital rack rates.

CLIENT QUESTION:
{question}

CLIENT RECORD:
{context}
"""
    content = _grok_chat(
        prompt,
        system='You are a private per-client wellness records bot. Never invent medical history.',
        temperature=0.3,
        timeout=45,
        max_model_attempts=1,
    )
    if content:
        return content.strip(), 'grok'
    err = get_last_grok_error()
    fallback = (
        f'{first}, your bot can see the records already in your portal. '
        'Ask about a specific test or add a past procedure in the form on this page.'
    )
    if err:
        fallback += f'\n\n{err}'
    return fallback, 'local'


def timeline_html(profile, documents):
    rows = []
    for item in (profile.get('procedures') or []):
        rows.append(
            f'<li><strong>{escape(item.get("date") or "undated")}</strong> — '
            f'{escape(item.get("title") or "Procedure")}'
            + (f' <span class="affiliate-note">{escape(item.get("notes") or "")}</span>' if item.get('notes') else '')
            + '</li>'
        )
    for item in timeline_from_documents(documents)[:20]:
        rows.append(
            f'<li><strong>{escape(item.get("date") or "undated")}</strong> — '
            f'{escape(item.get("title") or "Record")} '
            f'<span class="affiliate-note">uploaded</span></li>'
        )
    if not rows:
        return '<p>No procedures or lab files yet. Upload PDFs or add a past procedure below.</p>'
    return f'<ul class="bot-timeline">{{"".join(rows)}</ul>'
