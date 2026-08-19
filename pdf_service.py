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
.body-system-name { color: #0b3d2a; }
.body-system-def { font-size: 9pt; color: #555; }
.body-marker-list { margin: 4px 0; padding-left: 16px; font-size: 9pt; }

.health-overall-card, .health-age-hero { background: #e8f5f1; border: 1px solid #b8d9cf; padding: 14px; margin: 12px 0 16px; }
.health-score-number { font-size: 22pt; font-weight: bold; color: #0d7a4f; }
.health-score-bar { height: 10px; background: #dceae5; margin: 6px 0; }
.health-score-fill { height: 100%; background: #10b981; }
.health-score-scale { font-size: 8pt; color: #666; }
.health-overall-note { font-size: 9pt; color: #3d5c55; }
.health-score-pill { font-weight: bold; }

.stress-badge { font-size: 8pt; padding: 2px 6px; }
.stress-minor { background: #d4edda; color: #155724; }
.stress-moderate { background: #fff3cd; color: #856404; }
.stress-chronic { background: #ffe0e0; color: #c0392b; }
.stress-weakness { background: #f8d7da; color: #721c24; }
.stress-severe { background: #f5c6cb; color: #721c24; }

.scan-columns { margin: 8px 0; }
.scan-col { margin-bottom: 10px; }
.scan-list { margin: 4px 0; padding-left: 16px; }
.scan-remedy-card { border: 1px solid #eee; padding: 8px; margin: 6px 0; }
.scan-price { font-weight: bold; color: #0b3d2a; }
.scan-steps { margin: 6px 0; padding-left: 18px; }
.scan-disclaimer { font-size: 8pt; color: #666; margin-top: 20px; border-top: 1px solid #ddd; padding-top: 8px; }
.page-break { page-break-before: auto; }
"""


def _sanitize_html_for_pdf(html):
    """Strip tags/styles that break xhtml2pdf while keeping content readable."""
    if not html:
        return ''
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.I | re.S)
    html = re.sub(r'<details([^>]*)>', r'<div class="body-system-card"\1>', html, flags=re.I)
    html = re.sub(r'</details>', '</div>', html, flags=re.I)
    html = re.sub(r'<summary([^>]*)>', r'<div class="body-system-summary"\1>', html, flags=re.I)
    html = re.sub(r'</summary>', '</div>', html, flags=re.I)

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


def _cap_large_html(html, max_chars=450000):
    """Prevent xhtml2pdf from choking on extremely large marker dumps."""
    if not html or len(html) <= max_chars:
        return html
    head = html[:max_chars]
    cut = head.rfind('</div>')
    if cut > max_chars // 2:
        head = head[:cut + 6]
    return (
        head
        + '<p style="color:#666;font-size:9pt;margin-top:12px;">'
        + '[Additional detailed markers omitted from PDF for size. '
        + 'View the full report online for complete findings.]</p>'
    )


def save_report_pdf(report_html, output_path):
    """Convert report HTML to PDF and save to disk. Returns True on success."""
    try:
        parent = os.path.dirname(output_path) or '.'
        os.makedirs(parent, exist_ok=True)
        full_html = wrap_for_pdf(_cap_large_html(report_html or ''))
        with open(output_path, 'wb') as pdf_file:
            result = pisa.CreatePDF(src=full_html, dest=pdf_file, encoding='utf-8')
        if not os.path.isfile(output_path) or os.path.getsize(output_path) < 100:
            print(f'[Root Cause] PDF file missing or too small: {output_path}')
            return False
        if getattr(result, 'err', 0):
            print(f'[Root Cause] PDF create reported errors for {output_path} (file kept)')
        return True
    except Exception as exc:
        print(f'[Root Cause] PDF save failed: {exc}')
        import traceback
        traceback.print_exc()
        return False


def pdf_to_bytes(report_html):
    """Return PDF as bytes (for email attachment)."""
    try:
        full_html = wrap_for_pdf(_cap_large_html(report_html or ''))
        buffer = BytesIO()
        result = pisa.CreatePDF(src=full_html, dest=buffer, encoding='utf-8')
        if not buffer.getvalue() or len(buffer.getvalue()) < 100:
            print('[Root Cause] pdf_to_bytes produced empty output')
            return None
        if getattr(result, 'err', 0):
            print('[Root Cause] pdf_to_bytes reported errors (bytes kept)')
        return buffer.getvalue()
    except Exception as exc:
        print(f'[Root Cause] pdf_to_bytes failed: {exc}')
        return None
