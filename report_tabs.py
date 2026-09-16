"""In-page report tabs: Overview, Systems, Food, Supplements, Questions, Ask Grok."""
import re
from html import escape

TAB_CSS = """
.rc-tablist{display:flex;flex-wrap:wrap;gap:.4rem;margin:0 0 1rem;position:sticky;top:0;z-index:5;background:linear-gradient(#fff 70%,rgba(255,255,255,.92))}
.rc-tab{border:1px solid #c5ddd5;background:#fff;color:#0b3d2a;border-radius:999px;padding:.45rem .8rem;font-size:.85rem;font-weight:700;cursor:pointer;min-height:40px}
.rc-tab.is-active{background:#0b3d2a;color:#fff;border-color:#0b3d2a}
.rc-tab:focus-visible{outline:3px solid #0d5c4d;outline-offset:2px}
.rc-tab-panel:not(.is-active){display:none}
.rc-ask-card{border:1px solid #dceee8;border-radius:12px;padding:1rem;background:#f7fbf9}
.rc-ask-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 .85rem}
.rc-ask-chip,.rc-ask-open{border-radius:999px;padding:.45rem .75rem;font-weight:700;cursor:pointer;min-height:40px}
.rc-ask-chip{border:1px solid #c5ddd5;background:#fff;color:#0d5c4d}
.rc-ask-open{background:#0b3d2a;color:#fff;border:0}
.rc-q-list{margin:0;padding:0;list-style:none;display:grid;gap:.65rem}
.rc-q-list li{border:1px solid #f1e0c2;background:#fffaf3;border-radius:10px;padding:.75rem .85rem}
@media (max-width:720px){.rc-tab{flex:1 1 calc(50% - .3rem);text-align:center}}
@media print{.rc-tablist,.rc-ask-open,.rc-ask-chips{display:none!important}.rc-tab-panel{display:block!important}}
"""

TAB_JS = """<script>
(function(){
  var root = document.getElementById('rc-report-tabs');
  if (!root) return;
  var tabs = root.querySelectorAll('[data-tab]');
  var panels = root.querySelectorAll('[data-panel]');
  function show(id){
    tabs.forEach(function(t){
      var on = t.getAttribute('data-tab') === id;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    panels.forEach(function(p){ p.classList.toggle('is-active', p.getAttribute('data-panel') === id); });
    if (id === 'ask') {
      var input = document.getElementById('grok-input');
      var bubble = document.getElementById('grok-bubble');
      var panel = document.getElementById('grok-panel');
      if (bubble && panel && !panel.classList.contains('open')) bubble.click();
      if (input) { try { input.focus(); } catch (e) {} }
    }
    try { history.replaceState(null, '', '#tab-' + id); } catch (e) {}
  }
  tabs.forEach(function(t){ t.addEventListener('click', function(){ show(t.getAttribute('data-tab')); }); });
  root.querySelectorAll('[data-ask]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var q = btn.getAttribute('data-ask') || '';
      var input = document.getElementById('grok-input');
      var bubble = document.getElementById('grok-bubble');
      var panel = document.getElementById('grok-panel');
      if (bubble && panel && !panel.classList.contains('open')) bubble.click();
      if (input) { input.value = q; input.focus(); }
      var send = document.getElementById('grok-send');
      if (send && q) send.click();
    });
  });
  var hash = (location.hash || '').replace('#tab-', '').replace('#', '');
  var allowed = {overview:1, systems:1, food:1, supplements:1, questions:1, ask:1};
  show(allowed[hash] ? hash : 'overview');
})();
</script>"""

def _has(html, *needles):
    low = (html or '').lower()
    return any(n.lower() in low for n in needles)

def _extract_questions(html):
    items = []
    for m in re.finditer(r'<article class="sys-plain-card discuss">\s*<h4>[^<]+</h4>\s*<p>(.*?)</p>', html or '', re.I | re.S):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text and text not in items:
            items.append(text)
    for m in re.finditer(r'<p class="top3-step">\s*Simple first step:\s*(.*?)</p>', html or '', re.I | re.S):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text and text not in items:
            items.append('Would this first step fit my routine: ' + text)
    return items[:8]

def _extract_priority_titles(html):
    titles = re.findall(r'<div class="top3-head">\s*<h3>(.*?)</h3>', html or '', re.I | re.S)
    return [re.sub(r'<[^>]+>', '', t).strip() for t in titles if t.strip()][:3]

def _questions_panel(html):
    items = _extract_questions(html) or ['Which of my top priorities is worth a standard lab check first?', 'How should I describe these scan patterns without treating them as a diagnosis?']
    lis = ''.join('<li><h3>Question %s</h3><p>%s</p></li>' % (i, escape(q)) for i, q in enumerate(items, start=1))
    return '<section class="rc-tab-panel" data-panel="questions" id="tab-questions"><h2>Questions for your practitioner</h2><p>Bring these talking points to a licensed clinician. They are not lab orders or a treatment plan.</p><ol class="rc-q-list">' + lis + '</ol></section>'

def _ask_panel(html):
    chips = [('How do I read this wellness report?', 'How do I read this wellness report in plain English?'), ('What is a Health Score?', 'What does a Health Score mean on my Root Cause report?')]
    for title in _extract_priority_titles(html):
        chips.append(('Ask about ' + title, 'In plain English, what should I know about the %s pattern on my wellness scan?' % title))
    chip_html = ''.join('<button type="button" class="rc-ask-chip" data-ask="%s">%s</button>' % (escape(q, quote=True), escape(label)) for label, q in chips)
    return '<section class="rc-tab-panel" data-panel="ask" id="tab-ask"><div class="rc-ask-card"><h2>Ask Grok about this report</h2><p>Grok can explain a section in everyday language. Keep questions about this report. Answers are educational only - not medical advice.</p><div class="rc-ask-chips">' + chip_html + '</div><button type="button" class="rc-ask-open" data-ask="Help me understand my top priorities on this wellness report.">Open Ask Grok</button></div></section>'

def _classify_chunk(chunk):
    low = chunk.lower()
    if 'id="body-overview"' in low or 'body-system-card' in low or 'hormonal patterns' in low or 'metabolic patterns' in low or 'sleep patterns' in low:
        return 'systems'
    if 'sensitivit' in low or 'environmental' in low:
        return 'food'
    if 'optional support ideas' in low or 'scan-remedy-card' in low or 'nutritional patterns' in low:
        return 'supplements'
    return 'overview'

def _split_inner(inner):
    buckets = {k: [] for k in ('overview', 'systems', 'food', 'supplements')}
    pattern = re.compile(r'(<aside class="wellness-banner">.*?</aside>)|(<details class="glossary-panel".*?</details>)|(<section class="top3".*?</section>)|(<section[^>]*id="body-overview".*?</section>)|(<section class="scan-section.*?</section>)|(<header class="scan-cover">.*?</header>)|(<footer class="scan-disclaimer">.*?</footer>)', re.I | re.S)
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
    extra = ''.join(leftover).strip()
    if extra:
        buckets['overview'].insert(0, extra)
    return buckets

def apply_report_tabs(html):
    if not html or 'id="rc-report-tabs"' in html:
        return html
    if 'wellness-report' not in html and 'body-overview' not in html and 'top3' not in html:
        return html
    has_food = _has(html, 'Sensitivities', 'energetic sensitivity', 'Environmental')
    has_supp = _has(html, 'Optional support ideas', 'scan-remedy-card', 'Nutritional patterns')
    buttons = [('overview', 'Overview'), ('systems', 'Systems')]
    if has_food:
        buttons.append(('food', 'Food & environment sensitivities'))
    if has_supp:
        buttons.append(('supplements', 'Supplement ideas'))
    buttons.extend([('questions', 'Questions for your practitioner'), ('ask', 'Ask Grok about this report')])
    tablist = '<div class="rc-tablist" role="tablist" aria-label="Report sections">' + ''.join('<button type="button" class="rc-tab%s" role="tab" data-tab="%s" aria-controls="tab-%s" aria-selected="%s">%s</button>' % (' is-active' if i == 0 else '', key, key, 'true' if i == 0 else 'false', escape(label)) for i, (key, label) in enumerate(buttons)) + '</div>'
    match = re.search(r'(<div class="wellness-report"[^>]*>)(.*)</div>\s*$', html, re.S)
    if match:
        prefix, inner = match.group(1), match.group(2)
        styles = ''
        sm = re.match(r'(\s*<style>.*?</style>)', inner, re.S)
        if sm:
            styles = sm.group(1)
            inner = inner[sm.end():]
        buckets = _split_inner(inner)
        panels = []
        for key in ('overview', 'systems', 'food', 'supplements'):
            if key == 'food' and not has_food:
                continue
            if key == 'supplements' and not has_supp:
                continue
            body = ''.join(buckets.get(key) or []) or '<p>Nothing extra in this section. Use Overview or Ask Grok.</p>'
            panels.append('<section class="rc-tab-panel%s" data-panel="%s" id="tab-%s" role="tabpanel">%s</section>' % (' is-active' if key == 'overview' else '', key, key, body))
        panels.append(_questions_panel(html))
        panels.append(_ask_panel(html))
        html = prefix + styles + '<div id="rc-report-tabs">' + tablist + ''.join(panels) + '</div>' + TAB_JS + '</div>'
    else:
        html = '<div id="rc-report-tabs">' + tablist + html + _questions_panel(html) + _ask_panel(html) + '</div>' + TAB_JS
    if '.rc-tablist{' not in html:
        html = html.replace('</style>', TAB_CSS + '</style>', 1) if '</style>' in html else ('<style>' + TAB_CSS + '</style>' + html)
    return html
