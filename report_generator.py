"""Parse raw bioenergetic scan data into a professional HTML report."""
import re
from html import escape
from datetime import datetime

from affiliate_links import supplement_list_html, lab_list_html, match_supplement_link, match_lab_links
from scan_template import generate_template_report_html, uses_template_format

SEVERITY_HIGH = 70
SEVERITY_MODERATE = 45

CATEGORY_KEYWORDS = {
    "Digestive & Gut": [
        "stomach", "intestin", "colon", "gut", "digest", "pancrea", "liver",
        "gallbladder", "bowel", "gi tract", "esophag", "duodenum", "ileum",
    ],
    "Immune & Microbial": [
        "bacteria", "virus", "fungus", "yeast", "candida", "parasite", "worm",
        "microbe", "mold", "lyme", "immune", "pathogen", "protozoa",
    ],
    "Nervous & Stress": [
        "brain", "nerve", "adrenal", "stress", "pituitary", "hypothalamus",
        "autonomic", "sympathetic", "parasympathetic",
    ],
    "Hormonal & Endocrine": [
        "thyroid", "hormone", "estrogen", "progesterone", "testosterone",
        "cortisol", "insulin", "pancreas", "ovary", "prostate",
    ],
    "Nutritional & Metabolic": [
        "vitamin", "mineral", "amino", "protein", "fatty acid", "omega",
        "magnesium", "zinc", "iron", "calcium", "b12", "folate", "metabol",
    ],
    "Detox & Elimination": [
        "kidney", "bladder", "lymph", "detox", "heavy metal", "mercury",
        "lead", "aluminum", "toxin",
    ],
    "Structural & Circulatory": [
        "heart", "circulat", "blood", "bone", "joint", "spine", "muscle",
        "skin", "lung", "respirat",
    ],
}

SUPPLEMENT_MAP = {
    "Digestive & Gut": [
        "Digestive enzyme complex",
        "Broad-spectrum probiotics",
        "L-glutamine for gut lining support",
    ],
    "Immune & Microbial": [
        "Antimicrobial botanical blend (as directed)",
        "Immune-modulating mushroom complex",
        "Binders for mycotoxin support if indicated",
    ],
    "Nervous & Stress": [
        "Magnesium glycinate",
        "Adaptogenic adrenal support",
        "B-complex with methylfolate",
    ],
    "Hormonal & Endocrine": [
        "Thyroid-supporting nutrients (selenium, iodine as appropriate)",
        "Blood sugar balance support",
    ],
    "Nutritional & Metabolic": [
        "Targeted multimineral",
        "Vitamin D3 + K2",
        "Omega-3 fatty acids",
    ],
    "Detox & Elimination": [
        "Milk thistle / liver support",
        "N-acetylcysteine (NAC)",
        "Hydration + electrolyte support",
    ],
    "Structural & Circulatory": [
        "CoQ10 or mitochondrial support",
        "Anti-inflammatory omega-3",
    ],
}

LAB_MAP = {
    "Digestive & Gut": ["Comprehensive stool analysis", "Calprotectin or fecal inflammation markers"],
    "Immune & Microbial": ["IgG food sensitivity panel", "OAT or organic acids test"],
    "Nervous & Stress": ["Cortisol rhythm (AM/PM)", "Neurotransmitter metabolites (OAT)"],
    "Hormonal & Endocrine": ["Full thyroid panel (TSH, Free T3, Free T4, antibodies)", "Sex hormone panel"],
    "Nutritional & Metabolic": ["Zinc, ferritin, vitamin D, B12, folate", "Complete metabolic panel"],
    "Detox & Elimination": ["Heavy metals screen", "GGT, ALT, AST liver panel"],
    "Structural & Circulatory": ["Lipid panel", "hs-CRP inflammatory marker"],
}


def _extract_value(line):
    """Pull numeric stress/resonance value from a line if present."""
    patterns = [
        r"(\d{1,3})\s*%",
        r"[:=]\s*(\d{1,3})",
        r"\b(\d{1,3})\s*(?:out of|/)\s*100",
        r"stress[:\s]+(\d{1,3})",
        r"resonance[:\s]+(\d{1,3})",
        r"score[:\s]+(\d{1,3})",
    ]
    for pat in patterns:
        m = re.search(pat, line, re.I)
        if m:
            val = int(m.group(1))
            if 0 <= val <= 100:
                return val
    nums = re.findall(r"\b(\d{1,3})\b", line)
    for n in nums:
        v = int(n)
        if 10 <= v <= 100:
            return v
    return None


def _categorize(label):
    lower = label.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return cat
    return "General Findings"


def _parse_lines(raw_data):
    """Parse raw text into structured finding dicts."""
    findings = []
    seen = set()

    for raw_line in raw_data.splitlines():
        line = raw_line.strip()
        if not line or len(line) < 3:
            continue
        if re.match(r"^[-=_*#]{3,}$", line):
            continue
        if line.lower() in ("finding", "findings", "results", "scan results", "item"):
            continue

        value = _extract_value(line)
        label = line
        for sep in (":", "=", "|", "\t"):
            if sep in line:
                parts = [p.strip() for p in line.split(sep, 1)]
                if len(parts) == 2 and parts[0]:
                    label = parts[0]
                    if value is None:
                        value = _extract_value(parts[1])
                break

        label = re.sub(r"^[\d\.\)\-\*]+\s*", "", label).strip()
        if len(label) < 2:
            continue

        key = label.lower()
        if key in seen:
            continue
        seen.add(key)

        severity = "info"
        if value is not None:
            if value >= SEVERITY_HIGH:
                severity = "high"
            elif value >= SEVERITY_MODERATE:
                severity = "moderate"
            else:
                severity = "low"
        elif re.search(
            r"\b(severe|high|critical|stressed|imbalance|positive|detected|elevated)\b",
            line,
            re.I,
        ):
            severity = "moderate"

        findings.append({
            "label": label,
            "value": value,
            "severity": severity,
            "category": _categorize(label),
            "raw": line,
        })

    findings.sort(
        key=lambda f: (
            {"high": 0, "moderate": 1, "low": 2, "info": 3}[f["severity"]],
            -(f["value"] or 0),
        )
    )
    return findings


def _group_by_category(findings):
    groups = {}
    for f in findings:
        groups.setdefault(f["category"], []).append(f)
    return groups


def _severity_badge(severity):
    labels = {
        "high": ("High Priority", "badge-high"),
        "moderate": ("Moderate", "badge-moderate"),
        "low": ("Low", "badge-low"),
        "info": ("Noted", "badge-info"),
    }
    text, cls = labels.get(severity, ("Noted", "badge-info"))
    return f'<span class="severity-badge {cls}">{text}</span>'


def _recommendations(active_categories):
    supplements = []
    labs = []
    for cat in active_categories:
        for s in SUPPLEMENT_MAP.get(cat, []):
            if s not in supplements:
                supplements.append(s)
        for l in LAB_MAP.get(cat, []):
            if l not in labs:
                labs.append(l)
    if not supplements:
        supplements = [
            "High-quality multivitamin/mineral",
            "Digestive enzymes with meals",
            "Omega-3 and magnesium glycinate",
        ]
    if not labs:
        labs = [
            "Comprehensive metabolic panel",
            "Thyroid panel (TSH, Free T3/T4)",
            "Vitamin D, zinc, ferritin",
        ]
    return supplements[:8], labs[:8]


def generate_report_text(email, title, raw_data, ai_recommendations_html=None):
    """Plain-text version of the report for email delivery."""
    findings = _parse_lines(raw_data or "")
    high = [f for f in findings if f['severity'] == 'high']
    moderate = [f for f in findings if f['severity'] == 'moderate']
    active_cats = list({f['category'] for f in high + moderate}) or list({f['category'] for f in findings[:4]})
    supplements, labs = _recommendations(active_cats)
    date_str = datetime.now().strftime('%B %d, %Y')

    lines = [
        'ROOT CAUSE BIOENERGETIC REPORT',
        '=' * 40,
        f'Client: {email}',
        f'Title: {title}',
        f'Date: {date_str}',
        '',
        'EXECUTIVE SUMMARY',
        f'{len(findings)} markers reviewed.',
        f'High priority: {len(high)} | Moderate: {len(moderate)}',
        '',
        'TOP FINDINGS',
    ]
    for f in (high + moderate)[:8] or findings[:6]:
        val = f' — {f["value"]}%' if f['value'] else ''
        lines.append(f'  • {f["label"]}{val}')

    lines.extend(['', 'SUPPLEMENT SUGGESTIONS (Amazon)'])
    for s in supplements[:6]:
        _label, url = match_supplement_link(s)
        lines.append(f'  • {_label}: {url}')

    lines.extend(['', 'RECOMMENDED LABS (online ordering)'])
    for l in labs[:6]:
        providers = match_lab_links(l)
        urls = ', '.join(f'{name}: {url}' for name, url, _n in providers)
        lines.append(f'  • {l} — {urls}')

    if ai_recommendations_html:
        plain_ai = re.sub(r'<[^>]+>', '', ai_recommendations_html)
        plain_ai = re.sub(r'\s+', ' ', plain_ai).strip()
        lines.extend(['', 'PERSONALIZED HEALTH OPTIONS', plain_ai[:2000]])

    lines.extend([
        '',
        'This report is for educational purposes only.',
        'Log in to your client portal to view the full formatted report and PDF.',
        '',
        'Root Cause Bioenergetics',
    ])
    return '\n'.join(lines)


def generate_report_html(
    email, title, raw_data, ai_recommendations_html=None, client_name=None,
    prefer_template=False, blood_reconciliation_html=None,
):
    """Build a complete professional HTML report from raw scan paste."""
    if prefer_template or uses_template_format(raw_data or '', title=title):
        return generate_template_report_html(
            email, title, raw_data, client_name=client_name,
            ai_recommendations_html=ai_recommendations_html,
            blood_reconciliation_html=blood_reconciliation_html,
        )

    findings = _parse_lines(raw_data or "")
    groups = _group_by_category(findings)
    high_count = sum(1 for f in findings if f["severity"] == "high")
    mod_count = sum(1 for f in findings if f["severity"] == "moderate")

    active_cats = [
        c for c, items in groups.items()
        if any(i["severity"] in ("high", "moderate") for i in items)
    ]
    if not active_cats and groups:
        active_cats = list(groups.keys())[:4]

    supplements, labs = _recommendations(active_cats)
    date_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    if findings:
        summary = (
            f"Analysis identified <strong>{len(findings)}</strong> resonant markers "
            f"across your scan, including <strong>{high_count}</strong> high-priority "
            f"and <strong>{mod_count}</strong> moderate-priority areas requiring attention."
        )
    else:
        summary = (
            "Your scan data has been received. Review the pasted content below and "
            "schedule a follow-up consultation for personalized interpretation."
        )

    sections_html = ""
    for cat, items in sorted(groups.items()):
        rows = ""
        for item in items[:25]:
            val_html = ""
            if item["value"] is not None:
                bar_w = min(item["value"], 100)
                bar_cls = (
                    "bar-high" if item["severity"] == "high"
                    else "bar-moderate" if item["severity"] == "moderate"
                    else "bar-low"
                )
                val_html = (
                    f'<div class="stress-bar-wrap">'
                    f'<div class="stress-bar {bar_cls}" style="width:{bar_w}%"></div>'
                    f'<span class="stress-value">{item["value"]}%</span></div>'
                )
            rows += (
                f'<div class="finding-row">'
                f'<div class="finding-label">{escape(item["label"])}</div>'
                f'<div class="finding-meta">{_severity_badge(item["severity"])}{val_html}</div>'
                f'</div>'
            )
        sections_html += (
            f'<section class="report-section">'
            f'<h3>{escape(cat)}</h3>'
            f'<div class="findings-grid">{rows}</div>'
            f'</section>'
        )

    if not sections_html and raw_data.strip():
        sections_html = (
            '<section class="report-section">'
            '<h3>Analysis Overview</h3>'
            '<p>Your scan has been processed. Detailed findings are organized in the sections below.</p>'
            '</section>'
        )

    supp_html = supplement_list_html(supplements)
    lab_html = lab_list_html(labs)

    top_findings = [f for f in findings if f["severity"] in ("high", "moderate")][:6]
    if not top_findings:
        top_findings = findings[:6]
    top_html = "".join(
        f'<li><strong>{escape(f["label"])}</strong>'
        + (f' — {f["value"]}% stress' if f["value"] else "")
        + "</li>"
        for f in top_findings
    ) or "<li>See detailed sections below for full findings.</li>"

    return f"""<article class="bio-report">
  <header class="report-header">
    <div class="report-brand">
      <span class="brand-icon">🌿</span>
      <div>
        <p class="brand-tag">Root Cause Bioenergetics</p>
        <h2 class="report-title">{escape(title)}</h2>
      </div>
    </div>
    <div class="report-meta-grid">
      <div class="meta-item"><span class="meta-label">Client</span><span class="meta-value">{escape(email)}</span></div>
      <div class="meta-item"><span class="meta-label">Generated</span><span class="meta-value">{date_str}</span></div>
      <div class="meta-item"><span class="meta-label">Markers Reviewed</span><span class="meta-value">{len(findings)}</span></div>
    </div>
  </header>

  <section class="report-executive">
    <h3>Executive Summary</h3>
    <p>{summary}</p>
    <ul class="top-findings">{top_html}</ul>
  </section>

  {sections_html}

  {ai_recommendations_html or ''}

  <div class="report-columns">
    <section class="report-section rec-box">
      <h3>💊 Supplement Recommendations</h3>
      <p class="rec-note">Amazon affiliate links — compare prices. Discuss with your practitioner before starting any protocol.</p>
      <ul>{supp_html}</ul>
    </section>
    <section class="report-section rec-box">
      <h3>🩺 Recommended Conventional Labs</h3>
      <p class="rec-note">Low-cost walk-in and online lab options (Any Lab Test Now, Walk-In Lab, Ulta Lab Tests).</p>
      <ul>{lab_html}</ul>
    </section>
  </div>

  <footer class="report-footer">
    <p>This report is for educational and wellness purposes only. It does not replace medical diagnosis or treatment. Always consult a qualified healthcare provider.</p>
    <p class="report-id">Root Cause Bioenergetic Analysis • {date_str}</p>
  </footer>
</article>"""