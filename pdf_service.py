"""Generate printable PDF reports from HTML."""
import os
import re
from io import BytesIO

from xhtml2pdf import pisa

PDF_STYLES = """
@page { size: letter; margin: 0.55in 0.6in; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #2d3436; line-height: 1.45; }

.report-header { background: #0b3d2a; color: white; padding: 16px; margin-bottom: 16px; }
.report-title { font-size: 18pt; margin: 4px 0 0; }
.brand-tag { font-size: 8pt; text-transform: uppercase; letter-spacing: 1px; margin: 0; }
.report-meta-grid { margin-top: 12px; }
.meta-item { display: inline-block; margin-right: 20px; font-size: 9pt; }
.meta-label { font-weight: bold; }
.report-executive { background: #e8f5f1; padding: 12px; margin-bottom: 16px; border-left: 4px solid #1a8c7a; }
.report-section { margin-bottom: 14px; page-break-inside: avoid; }
.report-section h3 { color: #0b3d2a; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
.finding-row { padding: 6px 0; border-bottom: 1px solid #eee; }
.finding-label { font-weight: bold; }
.severity-badge { font-size: 8pt; padding: 2px 6px; border-radius: 3px; }
.badge-high { background: #ffe0e0; color: #c0392b; }
.badge-moderate { background: #fff3cd; color: #856404; }
.badge-low { background: #d4edda; color: #155724; }
.badge-info { background: #e2e3e5; color: #383d41; }
.rec-box { background: #f8faf9; padding: 10px; margin-bottom: 10px; }
.report-footer { font-size: 8pt; color: #666; margin-top: 20px; border-top: 1px solid #ddd; padding-top: 8px; }
.ai-section { background: #f0f7ff; padding: 12px; border-left: 4px solid #2980b9; margin: 16px 0; page-break-inside: avoid; }
ul { margin: 6px 0; padding-left: 18px; }

.scan-report { max-width: 100%; }
.scan-cover { text-align: center; padding: 18px 12px 24px; border-bottom: 3px solid #1a8c7a; margin-bottom: 18px; }
.scan-brand { font-size: 8pt; letter-spacing: 2px; text-transform: uppercase; color: #1a8c7a; margin: 0 0 8px; }
.scan-main-title { font-size: 22pt; color: #0b3d2a; margin: 0 0 6px; font-weight: bold; }
.scan-client-line { font-size: 13pt; color: #2d3436; margin: 0; }
.scan-client-email { font-size: 9pt; color: #666; margin: 4px 0 0; }

.scan-section { margin: 18px 0; page-break-inside: avoid; }
.scan-section h2 { color: #0b3d2a; font-size: 14pt; border-bottom: 2px solid #d4ebe4; padding-bottom: 4px; margin: 0 0 10px; }
.scan-section h4 { color: #1a5276; font-size: 10pt; margin: 8px 0 4px; }
.scan-lead { color: #555; font-size: 9.5pt; margin: 0 0 10px; }

.scan-legend { font-size: 8pt; color: #666; margin: 8px 0 12px; }
.scan-legend span { display: inline-block; margin-right: 10px; }

.body-overview-grid { margin-top: 10px; }
.body-system-card { border: 1px solid #dceee8; margin-bottom: 8px; page-break-inside: avoid; padding: 8px 10px; }
.body-system-summary { padding: 4px 0; font-weight: bold; }
.body-system-detail { padding: 4px 0 6px; font-size: 9pt; }
.stress-badge { padding: 2px 8px; border-radius: 10px; font-size: 8pt; font-weight: bold; }
.stress-minor { background: #d4edda; color: #155724; }
.stress-moderate { background: #e8f5e1; color: #3d6b2e; }
.stress-chronic { background: #fff3cd; color: #856404; }
.stress-weakness { background: #ffe8cc; color: #a05a00; }
.stress-severe { background: #f8d7da; color: #721c24; }

.health-overall-card { background: #e8f5f1; border: 1px solid #b8d9cf; padding: 12px 14px; margin: 12px 0 14px; }
.health-overall-header h3 { margin: 0 0 6px; font-size: 12pt; color: #0d5c4d; }
.health-score-number { font-size: 22pt; font-weight: bold; color: #0d7a4f; }
.health-score-number.health-excellent, .health-score-pill.health-excellent { color: #0d7a4f; }
.health-score-number.health-good, .health-score-pill.health-good { color: #2d8a4e; }
.health-score-number.health-fair, .health-score-pill.health-fair { color: #b8860b; }
.health-score-number.health-low, .health-score-pill.health-low { color: #c45c26; }
.health-score-number.health-critical, .health-score-pill.health-critical { color: #b33a3a; }
.health-overall-note { font-size: 9pt; color: #3d5c55; margin: 6px 0; }
.health-score-bar { height: 10px; background: #dceae5; margin: 4px 0; }
.health-score-fill { height: 10px; background: #059669; }
.health-score-fill.health-excellent { background: #059669; }
.health-score-fill.health-good { background: #10b981; }
.health-score-fill.health-fair { background: #d97706; }
.health-score-fill.health-low { background: #ea580c; }
.health-score-fill.health-critical { background: #dc2626; }
.health-score-scale { font-size: 7pt; color: #6b857e; }
.health-progress { font-size: 9pt; color: #0d7a4f; }
.health-score-pill { font-weight: bold; font-size: 10pt; padding: 2px 6px; background: #f0f9f6; }
.sys-progress { font-size: 8pt; color: #5a6f6a; }
.marker-summary { font-size: 9pt; margin: 4px 0; color: #3d5c55; }
.health-disclaimer-note { font-size: 8pt; color: #6b857e; margin-top: 10px; }

.scan-columns { display: block; margin-top: 8px; }
.scan-col { display: inline-block; width: 23%; vertical-align: top; padding: 0 1% 12px 0; }
.scan-list { margin: 0; padding-left: 14px; font-size: 9pt; }
.scan-muted { color: #888; font-size: 9pt; font-style: italic; }

.marker-card { background: #fafcfb; border: 1px solid #dceee8; padding: 10px 12px; margin: 10px 0; page-break-inside: avoid; }
.marker-title { color: #0b3d2a; font-size: 10pt; margin: 0 0 4px; }

.scan-summary p { margin: 0 0 10px; font-size: 10.5pt; line-height: 1.65; }
.scan-steps { margin: 8px 0 0; padding-left: 20px; }
.scan-remedy-category { color: #0b3d2a; font-size: 12pt; margin: 14px 0 6px; border-bottom: 1px solid #dceee8; }
.scan-remedy-card { border: 1px solid #e0e0e0; padding: 10px; margin: 8px 0; page-break-inside: avoid; }
.scan-price { font-weight: bold; color: #1a8c7a; }

.scan-disclaimer { margin-top: 24px; padding-top: 12px; border-top: 1px solid #ccc; font-size: 8pt; color: #666; }
.page-break { page-break-before: auto; }
"""


def _sanitize_html_for_pdf(html):
    """Strip tags/styles that break xhtml2pdf while keeping content readable."""
    if not html:
        return ''
    # Remove inline <style> blocks (Health Scores injects CSS; we use PDF_STYLES)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.I | re.S)
    # Convert <details>/<summary> to plain divs
    html = re.sub(r'<details([^>]*)>', r'<div class="body-system-card"\1>', html, flags=re.I)
    html = re.sub(r'</details>', '</div>', html, flags=re.I)
    html = re.sub(r'<summary([^>]*)>', r'<div class="body-system-summary"\1>', html, flags=re.I)
    html = re.sub(r'</summary>', '</div>', html, flags=re.I)
    # Keep only simple width styles for score bars
    def _clean_style(m):
        style = m.group(1) or ''
        widths = re.findall(r'width\s*:\s*[\d.]+%', style, flags=re.I)
        if widths:
            return f' style="{widths[0]}"'
        return ''
    html = re.sub(r'\sstyle="([^"]*)"', _clean_style, html, flags=re.I)
    return html


def wrap_for_pdf(report_html):
    """Wrap report HTML with PDF-friendly document structure."""
    safe = _sanitize_html_for_pdf(report_html or '')
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>{PDF_STYLES}</style>
</head>
<body>{safe}</body>
</html>"""


def save_report_pdf(report_html, output_path):
    """Convert report HTML to PDF and save to disk. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        full_html = wrap_for_pdf(report_html)
        with open(output_path, 'wb') as pdf_file:
            result = pisa.CreatePDF(full_html, dest=pdf_file, encoding='utf-8')
        if result.err:
            print(f'[Root Cause] PDF create reported errors for {output_path}')
            return False
        return True
    except Exception as exc:
        print(f'[Root Cause] PDF save failed: {exc}')
        return False


def pdf_to_bytes(report_html):
    """Return PDF as bytes (for email attachment)."""
    try:
        full_html = wrap_for_pdf(report_html)
        buffer = BytesIO()
        result = pisa.CreatePDF(full_html, dest=buffer, encoding='utf-8')
        if result.err:
            print('[Root Cause] pdf_to_bytes reported errors')
            return None
        return buffer.getvalue()
    except Exception as exc:
        print(f'[Root Cause] pdf_to_bytes failed: {exc}')
        return None
