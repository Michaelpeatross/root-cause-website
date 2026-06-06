"""Personalized supplements and lab recommendations for the client dashboard."""
from datetime import datetime

from report_generator import _parse_lines, _recommendations
from affiliate_links import supplement_list_html, lab_list_html
from document_service import filter_recent_medical_documents


def get_personalized_recommendations(latest_report, all_documents):
    """
    Build supplement and lab recommendation HTML from the latest approved scan
    plus medical documents from the past 12 months.
    """
    if not latest_report or not latest_report.raw_data:
        return {
            'supplements_html': '<p>Upload a scan or wait for your practitioner to publish your first report.</p>',
            'labs_html': '<p>Lab suggestions will appear after your first scan is published.</p>',
            'updated_at': None,
            'has_data': False,
        }

    findings = _parse_lines(latest_report.raw_data)
    high = [f for f in findings if f['severity'] == 'high']
    moderate = [f for f in findings if f['severity'] == 'moderate']
    active_cats = list({f['category'] for f in high + moderate})
    if not active_cats and findings:
        active_cats = list({f['category'] for f in findings[:8]})

    recent_docs = filter_recent_medical_documents(all_documents or [])
    if recent_docs:
        for doc in recent_docs:
            if doc.extracted_text:
                doc_findings = _parse_lines(doc.extracted_text[:5000])
                for f in doc_findings:
                    if f['category'] not in active_cats:
                        active_cats.append(f['category'])

    supplements, labs = _recommendations(active_cats[:8])

    updated = latest_report.analysis_updated or latest_report.approved_at or latest_report.date
    if recent_docs:
        updated = datetime.now().strftime('%Y-%m-%d %H:%M')

    doc_note = ''
    if recent_docs:
        doc_note = (
            f'<p class="rec-note"><em>Updated from your latest scan and '
            f'{len(recent_docs)} medical document(s) from the past 12 months.</em></p>'
        )

    return {
        'supplements_html': doc_note + f'<ul>{supplement_list_html(supplements)}</ul>',
        'labs_html': doc_note + f'<ul>{lab_list_html(labs)}</ul>',
        'ai_html': latest_report.ai_recommendations or '',
        'updated_at': updated,
        'has_data': True,
        'scan_title': latest_report.title,
    }