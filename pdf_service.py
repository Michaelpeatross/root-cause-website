"""Generate printable PDF reports from HTML."""
import os
from io import BytesIO

from xhtml2pdf import pisa

PDF_STYLES = """
@page { size: letter; margin: 0.6in; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; color: #2d3436; }
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
.ai-section { background: #f0f7ff; padding: 12px; border-left: 4px solid #2980b9; margin: 16px 0; }
ul { margin: 6px 0; padding-left: 18px; }
"""


def wrap_for_pdf(report_html):
    """Wrap report HTML with PDF-friendly document structure."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>{PDF_STYLES}</style>
</head>
<body>{report_html}</body>
</html>"""


def save_report_pdf(report_html, output_path):
    """Convert report HTML to PDF and save to disk. Returns True on success."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    full_html = wrap_for_pdf(report_html)
    with open(output_path, 'wb') as pdf_file:
        result = pisa.CreatePDF(full_html, dest=pdf_file, encoding='utf-8')
    return not result.err


def pdf_to_bytes(report_html):
    """Return PDF as bytes (for email attachment)."""
    full_html = wrap_for_pdf(report_html)
    buffer = BytesIO()
    result = pisa.CreatePDF(full_html, dest=buffer, encoding='utf-8')
    if result.err:
        return None
    return buffer.getvalue()