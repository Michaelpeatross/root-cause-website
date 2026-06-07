"""Generate printable PDF reports from HTML."""
import os
from io import BytesIO

from xhtml2pdf import pisa

PDF_STYLES = """
@page { size: letter; margin: 0.55in 0.6in; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #2d3436; line-height: 1.45; }

/* Legacy report styles */
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

/* Full Scan template styles */
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
.scan-section-intro { background: #f8faf9; padding: 10px; margin-bottom: 12px; border-left: 3px solid #1a8c7a; }

.scan-legend { font-size: 8pt; color: #666; margin: 8px 0 12px; }
.scan-legend span { display: inline-block; margin-right: 10px; }

.scan-systems-grid { margin: 10px 0; }
.scan-system-pill { display: inline-block; background: #e8f5f1; color: #0b3d2a; padding: 5px 10px; margin: 3px; border-radius: 4px; font-size: 9pt; font-weight: bold; }
.body-overview-grid { margin-top: 10px; }
.body-system-card { border: 1px solid #dceee8; margin-bottom: 8px; page-break-inside: avoid; }
.body-system-summary { padding: 8px 10px; font-weight: bold; }
.body-system-detail { padding: 0 10px 10px; font-size: 9pt; }
.stress-badge { padding: 2px 8px; border-radius: 10px; font-size: 8pt; font-weight: bold; }
.stress-minor { background: #d4edda; color: #155724; }
.stress-moderate { background: #e8f5e1; color: #3d6b2e; }
.stress-chronic { background: #fff3cd; color: #856404; }
.stress-weakness { background: #ffe8cc; color: #a05a00; }
.stress-severe { background: #f8d7da; color: #721c24; }

.scan-notes { background: #fff8e6; padding: 10px; margin-top: 10px; border-left: 3px solid #f0c040; }
.scan-notes h4 { margin-top: 0; color: #856404; }

.scan-columns { display: block; margin-top: 8px; }
.scan-col { display: inline-block; width: 23%; vertical-align: top; padding: 0 1% 12px 0; }
.scan-list { margin: 0; padding-left: 14px; font-size: 9pt; }
.scan-list li { margin-bottom: 2px; }
.scan-nutrient-block { font-size: 9pt; white-space: pre-wrap; margin: 0; }
.scan-muted { color: #888; font-size: 9pt; font-style: italic; }

.scan-imbalance-card,
.marker-card { background: #fafcfb; border: 1px solid #dceee8; padding: 10px 12px; margin: 10px 0; page-break-inside: avoid; }
.marker-title { color: #0b3d2a; font-size: 10pt; margin: 0 0 4px; }
.marker-subsection h3 { color: #0b3d2a; font-size: 11pt; margin: 12px 0 6px; }
.scan-imbalance-card h4 { color: #0b3d2a; font-size: 10pt; margin: 0 0 6px; text-transform: uppercase; }
.scan-imbalance-card p { margin: 4px 0; font-size: 9.5pt; }

.scan-hormone-item { margin: 8px 0; padding-bottom: 8px; border-bottom: 1px solid #eee; }
.scan-hormone-item h4 { margin: 0 0 4px; color: #1a5276; }

.scan-summary p { margin: 0 0 10px; font-size: 10.5pt; line-height: 1.65; }
.scan-prose p { margin: 0 0 10px; }
.scan-steps { margin: 8px 0 0; padding-left: 20px; }
.scan-steps li { margin-bottom: 8px; line-height: 1.55; }
.scan-remedy-category { color: #0b3d2a; font-size: 12pt; margin: 14px 0 6px; border-bottom: 1px solid #dceee8; }

.scan-remedy-card { border: 1px solid #e0e0e0; padding: 10px; margin: 8px 0; page-break-inside: avoid; }
.scan-remedy-card h4 { margin: 0 0 4px; color: #0b3d2a; }
.scan-remedy-card p { margin: 3px 0; font-size: 9pt; }
.scan-price { font-weight: bold; color: #1a8c7a; }

.scan-disclaimer { margin-top: 24px; padding-top: 12px; border-top: 1px solid #ccc; font-size: 8pt; color: #666; }
.scan-raw-fallback { font-size: 8pt; white-space: pre-wrap; background: #f5f5f5; padding: 10px; }

.page-break { page-break-before: auto; }
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