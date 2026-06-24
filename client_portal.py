"""Personalized supplements and lab recommendations for the client dashboard."""
import re
from datetime import datetime

from report_generator import _parse_lines, _recommendations
from affiliate_links import supplement_list_html, lab_list_html
from document_service import scan_text_has_content


def _extract_ranked_section(ai_html, heading_regex):
    """Extract the HTML list content following a specific <h4> heading from Grok AI HTML.
    Returns the inner list HTML (or empty) so dashboard cards show the specific ranked recs.
    """
    if not ai_html:
        return ''
    # Match the heading (case-insensitive) and capture following content until next h4 or end of section
    pattern = rf'<h4[^>]*>\s*{heading_regex}\s*</h4>\s*(<ol>|<ul>)(.*?)(</ol>|</ul>)\s*(?=<h4|<p class="rec-note"|$)' 
    m = re.search(pattern, ai_html, flags=re.IGNORECASE | re.DOTALL)
    if m:
        list_tag_open = m.group(1)
        inner = m.group(2).strip()
        list_tag_close = m.group(3)
        return f'{list_tag_open}{inner}{list_tag_close}'
    # Fallback: try broader grab of first ul/ol after any mention of the heading keywords
    if re.search(heading_regex, ai_html, re.I):
        # Grab the next list after the heading mention
        after = ai_html[re.search(heading_regex, ai_html, re.I).end():]
        m2 = re.search(r'(<ol>|<ul>)(.*?)(</ol>|</ul>)', after, re.I | re.DOTALL)
        if m2:
            return m2.group(1) + m2.group(2).strip() + m2.group(3)
    return ''


def _report_has_updates(report):
    """True when Grok analysis was refreshed after the original scan publish."""
    if not report:
        return False
    if report.analysis_updated:
        return True
    if report.blood_reconciliation_html:
        return True
    original = (report.original_ai_recommendations or '').strip()
    current = (report.ai_recommendations or '').strip()
    return bool(current and original and current != original)


def get_personalized_recommendations(latest_report, all_documents):
    """
    Build supplement and lab recommendation HTML from the latest approved scan
    plus all uploaded medical documents.
    """
    if not latest_report or not scan_text_has_content(latest_report.raw_data):
        return {
            'supplements_html': '<p>Your practitioner will publish your bio scan report here.</p>',
            'labs_html': '<p>Lab suggestions will appear after your first scan is published.</p>',
            'updated_at': None,
            'has_data': False,
            'has_updates': False,
        }

    findings = _parse_lines(latest_report.raw_data)
    high = [f for f in findings if f['severity'] == 'high']
    moderate = [f for f in findings if f['severity'] == 'moderate']
    active_cats = list({f['category'] for f in high + moderate})
    if not active_cats and findings:
        active_cats = list({f['category'] for f in findings[:8]})

    all_docs = all_documents or []
    for doc in all_docs:
        if doc.extracted_text:
            doc_findings = _parse_lines(doc.extracted_text[:5000])
            for f in doc_findings:
                if f['category'] not in active_cats:
                    active_cats.append(f['category'])

    supplements, labs = _recommendations(active_cats[:8])

    has_updates = _report_has_updates(latest_report)
    updated = latest_report.analysis_updated or latest_report.reconciled_at
    if not updated and has_updates:
        updated = latest_report.approved_at or latest_report.date

    original_ai = (
        latest_report.original_ai_recommendations
        or latest_report.ai_recommendations
        or ''
    )
    updated_ai = (latest_report.ai_recommendations or '') if has_updates else ''

    doc_note = ''
    if all_docs:
        doc_note = (
            f'<p class="rec-note"><em>Based on your bio scan and '
            f'{len(all_docs)} uploaded medical document(s).</em></p>'
        )

    # Prefer Grok's specific ranked recommendations (with 1-10 ranks + GoodLabs) so they appear
    # consistently in dashboard cards, report, email, and previous scan views.
    grok_supp = _extract_ranked_section(updated_ai or original_ai, r'Suggested Supplements')
    grok_labs = _extract_ranked_section(updated_ai or original_ai, r'Labs to Discuss')

    if grok_supp:
        supplements_html = doc_note + grok_supp
    else:
        supplements_html = doc_note + f'<ul>{supplement_list_html(supplements)}</ul>'

    if grok_labs:
        labs_html = doc_note + grok_labs
    else:
        labs_html = doc_note + f'<ul>{lab_list_html(labs)}</ul>'

    return {
        'supplements_html': supplements_html,
        'labs_html': labs_html,
        'original_ai_html': original_ai,
        'updated_ai_html': updated_ai,
        'ai_html': updated_ai or original_ai,
        'reconciliation_html': latest_report.blood_reconciliation_html or '',
        'reconciled_at': latest_report.reconciled_at,
        'updated_at': updated,
        'has_data': True,
        'has_updates': has_updates,
        'scan_title': latest_report.title,
        'scan_report_html': (
            latest_report.original_generated_report or latest_report.generated_report
        ),
    }