"""Interactive Grok Q&A and term explanations for client analysis views."""
import re
import time

from health_advisor import _grok_chat, get_last_grok_error
from report_generator import _parse_lines, LAB_MAP, SUPPLEMENT_MAP, CATEGORY_KEYWORDS
from document_service import combined_document_text

_GROK_RATE_LIMITS = {}
GROK_RATE_LIMIT_SECONDS = 7


def _normalize_email(email):
    return (email or '').strip().lower()


def check_grok_rate_limit(user_email, report_id):
    """Simple per-(user,report) cooldown to protect xAI usage. Returns (allowed, retry_after_seconds)."""
    if not report_id:
        return True, 0
    try:
        key = (_normalize_email(user_email), int(report_id))
    except (TypeError, ValueError):
        return True, 0
    now = time.monotonic()
    last = _GROK_RATE_LIMITS.get(key, 0)
    if now - last < GROK_RATE_LIMIT_SECONDS:
        return False, max(1, int(GROK_RATE_LIMIT_SECONDS - (now - last)))
    _GROK_RATE_LIMITS[key] = now
    # occasional prune to avoid unbounded growth
    if len(_GROK_RATE_LIMITS) > 300:
        cutoff = now - 600
        for k in list(_GROK_RATE_LIMITS.keys()):
            if _GROK_RATE_LIMITS[k] < cutoff:
                _GROK_RATE_LIMITS.pop(k, None)
    return True, 0

_TERM_STOPWORDS = frozenset({
    'the', 'and', 'for', 'with', 'your', 'scan', 'blood', 'test', 'may', 'can',
    'not', 'are', 'was', 'has', 'had', 'from', 'this', 'that', 'have', 'been',
    'will', 'all', 'any', 'one', 'two', 'new', 'old', 'see', 'use', 'used',
})

_WELLNESS_TERMS = (
    'bioenergetic', 'resonance', 'sensitivity', 'sensitivities', 'detox',
    'inflammation', 'metabolic', 'mitochondrial', 'microbiome', 'candida',
    'cortisol', 'thyroid', 'ferritin', 'cholesterol', 'lipid', 'antibody',
    'pathogen', 'parasite', 'homeopathic', 'homeopathics', 'adaptogen',
    'probiotic', 'prebiotic', 'enzyme', 'magnesium', 'selenium', 'folate',
    'homocysteine', 'hepatitis', 'gallbladder', 'pancreas', 'adrenal',
    'hypothalamus', 'pituitary', 'lymphatic', 'mycotoxin', 'heavy metal',
)


def collect_grok_terms(report):
    """Terms from scan findings and recommendations to hyperlink in analysis."""
    terms = set(_WELLNESS_TERMS)
    for cat in CATEGORY_KEYWORDS:
        terms.add(cat)
    for mapping in (LAB_MAP, SUPPLEMENT_MAP):
        for items in mapping.values():
            for item in items:
                terms.add(item)
                for part in re.split(r'[,/()]+', item):
                    part = part.strip()
                    if len(part) > 3:
                        terms.add(part)

    findings = _parse_lines(report.raw_data or '')
    for finding in findings:
        terms.add(finding['label'])
        terms.add(finding['category'])
        for word in re.findall(r'[A-Za-z][A-Za-z0-9\-]{2,}', finding['label']):
            if word.lower() not in _TERM_STOPWORDS:
                terms.add(word)

    for html in (
        report.original_ai_recommendations,
        report.ai_recommendations,
        report.blood_reconciliation_html,
    ):
        if not html:
            continue
        for match in re.findall(r'<strong[^>]*>(.*?)</strong>', html, re.I | re.S):
            plain = re.sub(r'<[^>]+>', '', match).strip()
            if plain and len(plain) > 2:
                terms.add(plain)

    cleaned = []
    seen = set()
    for term in terms:
        text = ' '.join(term.split())
        if len(text) < 3 or text.lower() in _TERM_STOPWORDS:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    cleaned = sorted(cleaned, key=len, reverse=True)
    # Cap to keep highlighting density reasonable and reduce noise in long reports
    MAX_TERMS = 75
    if len(cleaned) > MAX_TERMS:
        cleaned = cleaned[:MAX_TERMS]
    return cleaned


def _report_context(report, documents=None):
    """Compact context string for Grok prompts."""
    findings = _parse_lines(report.raw_data or '')[:20]
    finding_lines = [
        f"- {f['label']} ({f['category']})"
        for f in findings[:15]
    ]
    ai_html = (
        report.ai_recommendations
        or report.original_ai_recommendations
        or ''
    )
    plain_ai = re.sub(r'<[^>]+>', ' ', ai_html)
    plain_ai = re.sub(r'\s+', ' ', plain_ai).strip()[:2500]

    medical = ''
    if documents:
        medical = combined_document_text(documents)[:2000]

    parts = [
        f'Report: {report.title}',
        'Key scan findings:',
        '\n'.join(finding_lines) if finding_lines else '- (none parsed)',
    ]
    if plain_ai:
        parts.extend(['Analysis excerpt:', plain_ai])
    if medical:
        parts.extend(['Uploaded medical notes excerpt:', medical])
    return '\n'.join(parts)


def grok_explain_term(term, report, documents=None, client_name='Client'):
    """Explain a highlighted term using Grok. Returns (plain_text, source)."""
    term = (term or '').strip()
    if not term:
        return 'No term provided.', 'local'

    context = _report_context(report, documents)
    first = (client_name or 'Client').split()[0]
    prompt = f"""You are Grok, a friendly wellness educator for Root Cause Bioenergetics.

Client: {first}

Explain the term "{term}" in plain language (8th-grade reading level) for this client,
using their scan context when relevant. 2-4 short sentences max.
- Educational only — not medical advice or diagnosis.
- Do not recommend products or lab providers.
- No bullet lists.

CLIENT CONTEXT:
{context}

Respond with 2-4 short plain-text sentences only (no HTML, no markdown)."""

    content = _grok_chat(
        prompt,
        system='You explain health and wellness terms clearly and briefly.',
        temperature=0.25,
        timeout=35,
        max_model_attempts=1,
    )
    if content:
        return content.strip(), 'grok'

    err = get_last_grok_error()
    fallback = (
        f'{term} appears in your bioenergetic analysis. '
        f'It relates to patterns your scan highlighted — ask your practitioner '
        f'for personalized guidance.'
    )
    if err:
        fallback += '\n\n' + str(err)
    return fallback, 'local'


_PUBLIC_RATE_LIMITS = {}
PUBLIC_RATE_LIMIT_SECONDS = 10


def check_public_grok_rate_limit():
    """Simple cooldown for public scan Q&A (no login required)."""
    key = 'public'
    now = time.monotonic()
    last = _PUBLIC_RATE_LIMITS.get(key, 0)
    if now - last < PUBLIC_RATE_LIMIT_SECONDS:
        return False, max(1, int(PUBLIC_RATE_LIMIT_SECONDS - (now - last)))
    _PUBLIC_RATE_LIMITS[key] = now
    if len(_PUBLIC_RATE_LIMITS) > 100:
        cutoff = now - 300
        for k in list(_PUBLIC_RATE_LIMITS.keys()):
            if _PUBLIC_RATE_LIMITS[k] < cutoff:
                _PUBLIC_RATE_LIMITS.pop(k, None)
    return True, 0


def grok_public_scan_question(question):
    """General public Q&A about bioenergetic scans (no personal report context). Returns (plain_text, source)."""
    question = (question or '').strip()
    if not question:
        return 'Please enter a question about the scans.', 'local'

    prompt = f"""You are Grok, a friendly expert wellness educator for Root Cause Bioenergetics bioenergetic hair and saliva scans.

These scans use resonance testing to identify patterns related to sensitivities, toxins, metabolic function, organ systems (such as adrenal, thyroid, gut, liver, etc.), pathogens, inflammation, and more.

Answer the user's question about what the scans test for, how to understand typical results, common patterns, and general wellness context.

- Write for an average adult at an 8th-grade reading level.
- Keep responses to 2-5 short paragraphs.
- Educational only — never medical advice, diagnosis, or treatment recommendations.
- Do not recommend specific products, brands, or particular labs/providers.
- Be clear, encouraging, and direct.

USER QUESTION:
{question}

Respond ONLY with plain text paragraphs (no HTML, no markdown, no bullet lists unless very short)."""

    content = _grok_chat(
        prompt,
        system='You clearly explain bioenergetic scan testing concepts, what different findings typically indicate, and general result interpretation using only Root Cause educational knowledge.',
        temperature=0.3,
        timeout=40,
        max_model_attempts=1,
    )
    if content:
        return content.strip(), 'grok'

    err = get_last_grok_error()
    fallback = 'Grok is temporarily unavailable for general scan questions. Please try again shortly or reach out to your practitioner.'
    if err:
        fallback += '\n\n' + str(err)
    return fallback, 'local'


def grok_answer_question(question, report, documents=None, client_name='Client'):
    """Answer a free-form client question about their analysis. Returns (plain_text, source)."""
    question = (question or '').strip()
    if not question:
        return 'Please enter a question.', 'local'

    context = _report_context(report, documents)
    first = (client_name or 'Client').split()[0]
    prompt = f"""You are Grok, a friendly wellness advisor for Root Cause Bioenergetics.

Client: {first}

Answer the client's question about their bioenergetic scan and analysis.
Use the context below. Write for an average adult (8th-grade reading level).
- 2-5 short paragraphs max.
- Educational only — not medical advice or diagnosis.
- Do not recommend specific products or lab providers unless already in their report.
- Address {first} by first name once.

CLIENT QUESTION:
{question}

CLIENT CONTEXT:
{context}

Respond with plain text paragraphs only (no HTML, no markdown)."""

    content = _grok_chat(
        prompt,
        system='You answer wellness questions clearly using only the provided client context.',
        temperature=0.35,
        timeout=45,
        max_model_attempts=1,
    )
    if content:
        return content.strip(), 'grok'

    err = get_last_grok_error()
    fallback = (
        'Grok is temporarily unavailable. Your question was saved — '
        'please try again in a few minutes or contact your practitioner.'
    )
    if err:
        fallback += '\n\n' + str(err)
    return fallback, 'local'