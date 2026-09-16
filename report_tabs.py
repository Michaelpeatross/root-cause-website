"""In-page report tabs: Overview, Systems, Food, Supplements, Questions, Ask Grok."""
import re
from html import escape

TAB_CSS = """
.rc-tablist{display:flex;flex-wrap:wrap;gap:.4rem;margin:0 0 1rem;padding:.35rem 0 .45rem;position:sticky;top:0;z-index:5;background:linear-gradient(#fff 72%,rgba(255,255,255,.92))}
.rc-tab{border:1px solid #c5ddd5;background:#fff;color:#0b3d2a;border-radius:999px;padding:.45rem .8rem;font-size:.85rem;font-weight:700;cursor:pointer;min-height:40px}
.rc-tab.is-active{background:#0b3d2a;color:#fff;border-color:#0b3d2a}
.rc-tab:focus-visible{outline:3px solid #0d5c4d;outline-offset:2px}
.rc-tab-short{display:none}
.rc-tab-panel{margin:0 0 1rem}
.rc-tab-panel:not(.is-active){display:none}
.rc-ask-card{border:1px solid #dceee8;border-radius:12px;padding:1rem;background:#f7fbf9}
.rc-ask-card h2{margin:0 0 .4rem;color:#0b3d2a;font-size:1.15rem}
.rc-ask-card p{margin:0 0 .75rem;color:#334;line-height:1.45}
.rc-ask-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:0 0 .85rem}
.rc-ask-chip{border:1px solid #c5ddd5;background:#fff;border-radius:999px;padding:.4rem .7rem;font-size:.82rem;cursor:pointer;color:#0d5c4d;font-weight:600;min-height:40px}
.rc-ask-open{background:#0b3d2a;color:#fff;border:0;border-radius:999px;padding:.55rem 1rem;font-weight:700;cursor:pointer;min-height:44px}
.rc-ask-compose{display:flex;gap:.45rem;flex-wrap:wrap;margin:.15rem 0 .85rem}
.rc-ask-compose input{flex:1 1 220px;min-height:44px;border:1px solid #c5ddd5;border-radius:999px;padding:.45rem .9rem;font-size:.95rem}
.rc-section-ask{margin:.65rem 0 0}
.rc-q-list{margin:0;padding:0;list-style:none;display:grid;gap:.65rem}
.rc-q-list li{border:1px solid #f1e0c2;background:#fffaf3;border-radius:10px;padding:.75rem .85rem}
.rc-q-list h3{margin:0 0 .3rem;color:#0b3d2a;font-size:.95rem}
.rc-q-list p{margin:0;color:#334;font-size:.9rem;line-height:1.45}
@media (max-width:720px){.rc-tablist{gap:.3rem}.rc-tab{flex:1 1 calc(50% - .3rem);text-align:center;padding:.4rem .55rem;font-size:.8rem}.rc-tab-full{display:none}.rc-tab-short{display:inline}}
@media print{.rc-tablist,.rc-ask-open,.rc-ask-chips,.rc-ask-compose,.rc-section-ask{display:none!important}.rc-tab-panel{display:block!important}}
"""

TAB_JS = """
<script>
(function(){
  var root = document.getElementById('rc-report-tabs');
  if (!root) return;
  var tabs = root.querySelectorAll('[data-tab]');
  var panels = root.querySelectorAll('[data-panel]');
  function openGrok(q, send){
    var input = document.getElementById('grok-input');
    var bubble = document.getElementById('grok-bubble');
    var panel = document.getElementById('grok-panel');
    if (typeof window.__openAskGrok === 'function') window.__openAskGrok();
    else if (bubble && panel && !panel.classList.contains('open')) bubble.click();
    if (input && q) { input.value = q; try { input.focus(); } catch (e) {} }
    if (send && q) { var sendBtn = document.getElementById('grok-send'); if (sendBtn) sendBtn.click(); }
  }
  function show(id){
    tabs.forEach(function(t){
      var on = t.getAttribute('data-tab') === id;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.setAttribute('tabindex', on ? '0' : '-1');
    });
    panels.forEach(function(p){
      var on = p.getAttribute('data-panel') === id;
      p.classList.toggle('is-active', on);
      if (on) p.removeAttribute('hidden'); else p.setAttribute('hidden', 'hidden');
    });
    if (id === 'ask') openGrok('', false);
    try { history.replaceState(null, '', '#tab-' + id); } catch (e) {}
  }
  tabs.forEach(function(t, idx){
    t.addEventListener('click', function(){ show(t.getAttribute('data-tab')); });
    t.addEventListener('keydown', function(ev){
      if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') return;
      ev.preventDefault();
      var next = ev.key === 'ArrowRight' ? (idx + 1) % tabs.length : (idx - 1 + tabs.length) % tabs.length;
      tabs[next].focus();
      show(tabs[next].getAttribute('data-tab'));
    });
  });
  root.querySelectorAll('[data-ask]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var q = btn.getAttribute('data-ask') || '';
      openGrok(q, !!q);
      show('ask');
    });
  });
  var box = root.querySelector('[data-ask-input]');
  var go = root.querySelector('[data-ask-submit]');
  if (box && go) {
    function sendTyped(){
      var q = (box.value || '').trim();
      if (!q) q = 'Help me understand my top priorities on this wellness report.';
      openGrok(q, true);
    }
    go.addEventListener('click', sendTyped);
    box.addEventListener('keydown', function(ev){ if (ev.key === 'Enter') { ev.preventDefault(); sendTyped(); } });
  }
  var hash = (location.hash || '').replace('#tab-', '').replace('#', '');
  var allowed = {overview:1, systems:1, food:1, supplements:1, questions:1, ask:1};
  show(allowed[hash] ? hash : 'overview');
})();
</script>
"""


def _has(html, *needles):
    low = (html or '').lower()
    return any(n.lower() in low for n in needles)


def _extract_questions(html):
    items = []
    for m in re.finditer(r'<article class="sys-plain-card discuss">.*?<h4>[^<]+</h4>.*?<p>(.*?)</p>', html or '', re.I | re.S):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text and text not in items:
            items.append(text)
    for m in re.finditer(r'<p class="top3-step">.*?Simple first step:(.*?)</p>', html or '', re.I | re.S):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text and text not in items:
            items.append('Would this first step fit my routine: ' + text)
    return items[:8]


def _extract_priority_titles(html):
    titles = re.findall(r'<div class="top3-head">.*?<h3>(.*?)</h3>', html or '', re.I | re.S)
    clean = [re.sub(r'<[^>]+>', '', t).strip() for t in titles]
    return [t for t in clean if t][:3]


def _section_ask(label, prompt):
    return ('<p class="rc-section-ask"><button type="button" class="rc-ask-chip" data-ask="%s">Ask Grok about %s</button></p>' % (escape(prompt, quote=True), escape(label)))


def _questions_panel(html):
    items = _extract_questions(html) or [
        'Which of my top priorities is worth a standard lab check first?',
        'How should I describe these scan patterns without treating them as a diagnosis?',
    ]
    lis = ''.join('<li><h3>Question %s</h3><p>%s</p></li>' % (i, escape(q)) for i, q in enumerate(items, start=1))
    return ('<section class="rc-tab-panel" data-panel="questions" id="tab-questions" role="tabpanel"><h2>Questions for your practitioner</h2><p>Bring these talking points to a licensed clinician. They are not lab orders or a treatment plan.</p><ol class="rc-q-list">' + lis + '</ol>' + _section_ask('these talking points', 'Help me turn my wellness-report talking points into a short list I can bring to my practitioner. Remind me this is not a diagnosis.') + '</section>')


def _ask_panel(html, has_food=False, has_supp=False):
    titles = _extract_priority_titles(html)
    chips = [
        ('How do I read this report?', 'How do I read this wellness report in plain English?'),
        ('What is a Health Score?', 'What does a Health Score mean on my Root Cause report?'),
        ('What should I tell my practitioner?', 'What talking points from this wellness report should I mention to my practitioner? Remind me this is not a diagnosis.'),
    ]
    for title in titles:
        chips.append(('Ask about ' + title, 'In plain English, what should I know about the %s pattern on my wellness scan?' % title))
    if has_food:
        chips.append(('Is this an allergy test?', 'Explain that the Food and environment sensitivities section is an energetic pattern, not an allergy test or diagnosis.'))
    if has_supp:
        chips.append(('What are support ideas?', 'Explain the Optional support ideas on my wellness report in everyday language. They are not prescriptions or dosing instructions.'))
    chip_html = ''.join('<button type="button" class="rc-ask-chip" data-ask="%s">%s</button>' % (escape(q, quote=True), escape(label)) for label, q in chips[:8])
    return ('<section class="rc-tab-panel" data-panel="ask" id="tab-ask" role="tabpanel"><div class="rc-ask-card"><h2>Ask Grok about this report</h2><p>Type a question about <em>this</em> report, or tap a chip. Answers are educational only — not medical advice.</p><div class="rc-ask-compose"><input type="text" data-ask-input maxlength="240" placeholder="e.g. What should I know about my top priority?"><button type="button" class="rc-ask-open" data-ask-submit>Ask Grok</button></div><div class="rc-ask-chips">' + chip_html + '</div><button type="button" class="rc-ask-open" data-ask="">Open chat</button></div></section>')


def _classify_chunk(chunk):
    low = chunk.lower()
    if 'sensitivit' in low or 'environmental' in low or '<h2>toxins</h2>' in low or 'energetic toxin' in low:
        return 'food'
    if 'optional support ideas' in low or 'scan-remedy-card' in low or 'balancing remed' in low or 'nutritional patterns' in low or 'nutritional imbalance' in low:
        return 'supplements'
    if 'id="body-overview"' in low or 'body-system-card' in low or 'hormonal' in low or 'metabolic' in low or 'sleep pattern' in low or 'sleep marker' in low:
        return 'systems'
    return 'overview'


def _split_inner(inner):
    buckets = {k: [] for k in ('overview', 'systems', 'food', 'supplements')}
    pattern = re.compile(r'(<aside class="wellness-banner">.*?</aside>)|(<details class="glossary-panel".*?</details>)|(<section class="top3".*?</section>)|(<div class="wellness-theme-grid">.*?</div>)|(<section[^>]*id="body-overview".*?</section>)|(<section class="scan-section.*?</section>)|(<header class="scan-cover">.*?</header>)|(<footer class="scan-disclaimer">.*?</footer>)', re.I | re.S)
    pos = 0
    leftover = []
    for m in pattern.finditer(inner):
        if m.start() > pos:
            leftover.append(inner[pos:m.start()])
        chunk = m.group(0)
        if chunk.lower().startswith('<footer'):
            leftover.append(chunk)
        else:
            buckets[_classify_chunk(chunk)].append(chunk)
        pos = m.end()
    if pos < len(inner):
        leftover.append(inner[pos:])
    extra = re.sub(r'</?article[^>]*>', '', ''.join(leftover)).strip()
    if extra:
        buckets['overview'].insert(0, extra)
    return buckets


def apply_report_tabs(html):
    if not html or 'id="rc-report-tabs"' in html:
        return html
    if 'wellness-report' not in html and 'body-overview' not in html and 'top3' not in html:
        return html
    has_food = _has(html, 'Sensitivities', 'energetic sensitivity', 'Environmental', 'Toxins')
    has_supp = _has(html, 'Optional support ideas', 'scan-remedy-card', 'Nutritional', 'Balancing Remedies')
    buttons = [('overview', 'Overview', 'Overview'), ('systems', 'Systems', 'Systems')]
    if has_food:
        buttons.append(('food', 'Food & environment sensitivities', 'Sensitivities'))
    if has_supp:
        buttons.append(('supplements', 'Supplement ideas', 'Supplements'))
    buttons.extend([('questions', 'Questions for your practitioner', 'Questions'), ('ask', 'Ask Grok about this report', 'Ask Grok')])
    tablist = '<div class="rc-tablist" role="tablist" aria-label="Report sections">' + ''.join('<button type="button" class="rc-tab%s" role="tab" data-tab="%s" aria-controls="tab-%s" aria-selected="%s" tabindex="%s"><span class="rc-tab-full">%s</span><span class="rc-tab-short">%s</span></button>' % (' is-active' if i == 0 else '', key, key, 'true' if i == 0 else 'false', '0' if i == 0 else '-1', escape(full), escape(short)) for i, (key, full, short) in enumerate(buttons)) + '</div>'
    match = re.search(r'(<div class="wellness-report"[^>]*>)(.*)</div>', html, re.S)
    if match:
        prefix, inner = match.group(1), match.group(2)
        styles = ''
        sm = re.match(r'(<style>.*?</style>)', inner.strip()[:1] and inner, re.S)
        if inner.lstrip().startswith('<style>'):
            sm = re.match(r'(.*?<style>.*?</style>)', inner, re.S)
            if sm:
                styles = sm.group(1)
                inner = inner[sm.end():]
        buckets = _split_inner(inner)
        panels = []
        section_prompts = {
            'systems': ('my body systems', 'In plain English, what should I notice in the Systems section of my wellness report?'),
            'food': ('sensitivities', 'Explain the Food and environment sensitivities section. Remind me this is not an allergy test.'),
            'supplements': ('support ideas', 'Explain the Supplement ideas on my wellness report. They are educational, not prescriptions.'),
        }
        for key in ('overview', 'systems', 'food', 'supplements'):
            if key == 'food' and not has_food:
                continue
            if key == 'supplements' and not has_supp:
                continue
            body = ''.join(buckets.get(key) or []) or '<p>Nothing extra in this section. Use Overview or Ask Grok.</p>'
            if key in section_prompts:
                label, prompt = section_prompts[key]
                body += _section_ask(label, prompt)
            panels.append('<section class="rc-tab-panel%s" data-panel="%s" id="tab-%s" role="tabpanel"%s>%s</section>' % (' is-active' if key == 'overview' else '', key, key, '' if key == 'overview' else ' hidden', body))
        panels.append(_questions_panel(html))
        panels.append(_ask_panel(html, has_food=has_food, has_supp=has_supp))
        html = prefix + styles + '<div id="rc-report-tabs">' + tablist + ''.join(panels) + '</div>' + TAB_JS + '</div>'
    else:
        html = '<div id="rc-report-tabs">' + tablist + html + _questions_panel(html) + _ask_panel(html, has_food, has_supp) + '</div>' + TAB_JS
    if '.rc-tablist{' not in html:
        html = html.replace('</style>', TAB_CSS + '</style>', 1) if '</style>' in html else ('<style>' + TAB_CSS + '</style>' + html)
    return html
