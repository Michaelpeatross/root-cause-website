"""Handle client medical document uploads and text extraction."""
import os
import re
import uuid
from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp',
    '.doc', '.docx', '.heic', '.heif',
    '.zip', '.xml', '.csv', '.json',  # for health/wearable data exports (Apple Health, Fitbit, etc.)
}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # allow most Apple Health zips so clients can usually upload directly
MAX_FILES_PER_UPLOAD = 25


def allowed_file(filename):
    ext = os.path.splitext(filename or '')[1].lower()
    return ext in ALLOWED_EXTENSIONS


def save_upload(file_storage, upload_dir):
    """Save uploaded file; returns (stored_name, original_name) or raises ValueError."""
    if not file_storage or not file_storage.filename:
        raise ValueError('No file selected.')

    original = secure_filename(file_storage.filename)
    if not allowed_file(original):
        raise ValueError(
            f'"{original}" type not allowed. Use PDF, images (PNG/JPG/WEBP/GIF), TXT, DOC/DOCX, or health data exports (ZIP, XML, CSV, JSON).'
        )

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError('File too large (max 100 MB).')

    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(original)[1].lower()
    stored = f'{uuid.uuid4().hex}{ext}'
    path = os.path.join(upload_dir, stored)
    file_storage.save(path)
    return stored, original


def save_multiple_uploads(file_list, upload_dir):
    """Save multiple uploaded files. Returns list of (stored, original) tuples."""
    valid = [f for f in (file_list or []) if f and f.filename]
    if not valid:
        raise ValueError('Select at least one file to upload.')
    if len(valid) > MAX_FILES_PER_UPLOAD:
        raise ValueError(f'Maximum {MAX_FILES_PER_UPLOAD} files per upload.')

    results = []
    errors = []
    for file_storage in valid:
        try:
            results.append(save_upload(file_storage, upload_dir))
        except ValueError as exc:
            errors.append(str(exc))

    if not results and errors:
        raise ValueError(' '.join(errors))
    if errors and results:
        return results, errors
    return results, []


def _pdf_extraction_failed(text):
    return (text or '').startswith('[PDF uploaded:')


def _validate_pdf_file(path, original_name):
    """Reject corrupt or non-PDF uploads before report generation."""
    size = os.path.getsize(path)
    if size < 512:
        raise ValueError(
            f'"{original_name}" is only {size} bytes — the upload looks corrupt or empty. '
            'Re-download the Full Scan PDF from your scanner software and try again.'
        )
    with open(path, 'rb') as handle:
        if not handle.read(5).startswith(b'%PDF'):
            raise ValueError(f'"{original_name}" is not a valid PDF file.')
    try:
        import fitz
        doc = fitz.open(path)
        try:
            if len(doc) < 1:
                raise ValueError(f'"{original_name}" has no pages.')
        finally:
            doc.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            f'"{original_name}" could not be opened as a PDF ({exc}).'
        ) from exc


def _ocr_pdf_text(file_path, max_pages=40, max_chars=60000):
    """Optional Tesseract OCR via PyMuPDF when the PDF has no text layer."""
    try:
        import fitz
    except ImportError:
        return ''

    try:
        doc = fitz.open(file_path)
    except Exception:
        return ''

    parts = []
    try:
        for i in range(min(len(doc), max_pages)):
            page = doc[i]
            try:
                tp = page.get_textpage_ocr(flags=0, language='eng', dpi=200, full=True)
                page_text = page.get_text(textpage=tp) or ''
            except Exception:
                page_text = ''
            if page_text.strip():
                parts.append(page_text)
    finally:
        doc.close()

    text = '\n'.join(parts).strip()
    if len(text) >= 80:
        return text[:max_chars]
    return ''


def _grok_vision_pdf_text(file_path, max_pages=10, max_chars=60000):
    """Last-resort scan text extraction using Grok vision on rendered PDF pages."""
    try:
        from health_advisor import grok_extract_pdf_scan_text
        return grok_extract_pdf_scan_text(
            file_path, max_pages=max_pages, max_chars=max_chars,
        )
    except Exception:
        return ''


def _extract_pdf_text(file_path, max_pages=40, max_chars=60000, allow_grok_vision=True):
    """Extract text from a PDF using multiple backends for vendor scan compatibility."""
    parts = []

    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path, strict=False)
        if getattr(reader, 'is_encrypted', False):
            try:
                reader.decrypt('')
            except Exception:
                pass
        for page in reader.pages[:max_pages]:
            parts.append(page.extract_text() or '')
        text = '\n'.join(parts).strip()
        if len(text) >= 80:
            return text[:max_chars]
    except Exception:
        pass

    try:
        import fitz
        doc = fitz.open(file_path)
        try:
            parts = []
            for i in range(min(len(doc), max_pages)):
                page = doc[i]
                page_text = page.get_text('text') or ''
                if len(page_text.strip()) < 40:
                    blocks = page.get_text('blocks') or []
                    block_text = '\n'.join(
                        b[4] for b in blocks if len(b) > 4 and isinstance(b[4], str)
                    )
                    if len(block_text.strip()) > len(page_text.strip()):
                        page_text = block_text
                parts.append(page_text)
            text = '\n'.join(parts).strip()
            if len(text) >= 80:
                return text[:max_chars]
        finally:
            doc.close()
    except Exception:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = '\n'.join(
                (page.extract_text() or '') for page in pdf.pages[:max_pages]
            ).strip()
            if len(text) >= 80:
                return text[:max_chars]
    except Exception:
        pass

    ocr_text = _ocr_pdf_text(file_path, max_pages=max_pages, max_chars=max_chars)
    if len(ocr_text) >= 80:
        return ocr_text

    if allow_grok_vision:
        vision_text = _grok_vision_pdf_text(
            file_path, max_pages=min(max_pages, 6), max_chars=max_chars,
        )
        if len(vision_text) >= 80:
            return vision_text

    return ''


def extract_text(file_path, original_name, *, max_pages=30, max_chars=20000, allow_grok_vision=True):
    """Extract readable text from an uploaded document."""
    ext = os.path.splitext(original_name or file_path)[1].lower()

    if ext == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()[:max_chars]

    if ext == '.pdf':
        text = _extract_pdf_text(
            file_path,
            max_pages=max_pages,
            max_chars=max_chars,
            allow_grok_vision=allow_grok_vision,
        )
        if text:
            return text
        return f'[PDF uploaded: {original_name} — text extraction unavailable]'

    if ext == '.docx':
        try:
            from docx import Document
            doc = Document(file_path)
            return '\n'.join(p.text for p in doc.paragraphs if p.text)[:20000]
        except Exception:
            return f'[Word document uploaded: {original_name}]'

    if ext in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.heic', '.heif'}:
        return f'[Medical image/screenshot uploaded: {original_name} — review with your practitioner]'

    if ext == '.zip':
        try:
            import zipfile
            with zipfile.ZipFile(file_path, 'r') as z:
                xml_members = [n for n in z.namelist() if n.lower().endswith('.xml') or 'export' in n.lower()]
                if xml_members:
                    info = z.getinfo(xml_members[0])
                    # Always try to summarize recent data (the parser uses bounded deques so it only keeps newest readings).
                    # This lets clients usually just upload the full zip.
                    with z.open(xml_members[0]) as f:
                        summary = _summarize_apple_health_xml(f)
                        return f'[Apple Health / Wearable Data Summary from {xml_members[0]}]\n{summary}'
                members = ', '.join(z.namelist()[:8])
                return f'[ZIP archive uploaded: {original_name} containing: {members} ...]'
        except Exception:
            return f'[ZIP archive uploaded: {original_name} — extraction failed]'

    if ext == '.xml':
        try:
            # Try to summarize even large direct .xml files (recent-only logic keeps memory low)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # peek first 1k to decide
                peek = f.read(1000)
                f.seek(0)
                if 'HKQuantityType' in peek or 'Record' in peek:
                    summary = _summarize_apple_health_xml(f)
                    return f'[Apple Health / Wearable Data Summary]\n{summary}'
                content = peek + f.read(4000)
                return f'[XML document]\n{content}\n[... truncated ...]'
        except Exception:
            return f'[XML uploaded: {original_name}]'

    if ext == '.csv':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [line.strip() for line in f.readlines()[:50]]
                return '[CSV health data summary (first 50 lines)]\n' + '\n'.join(lines)
        except Exception:
            return f'[CSV uploaded: {original_name}]'

    if ext == '.json':
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                text = json.dumps(data, indent=2)[:4000]
                return f'[JSON health data summary]\n{text}\n[... truncated ...]'
        except Exception:
            return f'[JSON uploaded: {original_name}]'

    return f'[Document uploaded: {original_name}]'


def _summarize_apple_health_xml(xml_file_or_content, max_records: int = 30) -> str:
    """Parse Apple Health XML and return a compact summary focused on RECENT data.
    Uses bounded deques so full multi-GB history exports still only keep the newest samples.
    Safe for large client uploads.
    """
    try:
        from collections import deque
        import xml.etree.ElementTree as ET

        # We keep only the most recent values per metric (newest data wins)
        metrics = {}          # rtype -> deque of recent values
        recent_samples = deque(maxlen=max_records)
        count = 0
        MAX_ITER = 5000       # safety cap - we can scan more now because we don't store everything

        def add_value(rtype, val, unit, date):
            if rtype not in metrics:
                metrics[rtype] = deque(maxlen=200)  # keep last ~200 readings per metric
            metrics[rtype].append(val)
            recent_samples.append(f"{date} {rtype}: {val} {unit}")

        if isinstance(xml_file_or_content, str):
            root = ET.fromstring(xml_file_or_content)
            for record in root.findall('.//Record'):
                if count >= MAX_ITER:
                    break
                count += 1
                rtype = record.get('type', '').replace('HKQuantityTypeIdentifier', '').replace('HKCategoryTypeIdentifier', '')
                value = record.get('value')
                unit = record.get('unit', '')
                date = record.get('startDate', '')[:10]
                if not value:
                    continue
                try:
                    val = float(value)
                except:
                    continue
                if any(k in rtype for k in ['HeartRate', 'RestingHeartRate', 'StepCount', 'Distance', 'ActiveEnergy', 'FlightsClimbed', 'Sleep', 'HeartRateVariability']):
                    add_value(rtype, val, unit, date)
        else:
            context = ET.iterparse(xml_file_or_content, events=('end',))
            for event, elem in context:
                if elem.tag == 'Record':
                    if count >= MAX_ITER:
                        elem.clear()
                        break
                    count += 1
                    rtype = elem.get('type', '').replace('HKQuantityTypeIdentifier', '').replace('HKCategoryTypeIdentifier', '')
                    value = elem.get('value')
                    unit = elem.get('unit', '')
                    date = elem.get('startDate', '')[:10]
                    if value:
                        try:
                            val = float(value)
                            if any(k in rtype for k in ['HeartRate', 'RestingHeartRate', 'StepCount', 'Distance', 'ActiveEnergy', 'FlightsClimbed', 'Sleep', 'HeartRateVariability']):
                                add_value(rtype, val, unit, date)
                        except:
                            pass
                    elem.clear()

        summary_lines = []
        for k, vals in metrics.items():
            if not vals:
                continue
            vlist = list(vals)  # last N values
            avg = sum(vlist) / len(vlist)
            summary_lines.append(f"{k}: recent avg={avg:.1f}, min={min(vlist):.1f}, max={max(vlist):.1f} ({len(vlist)} samples)")

        if recent_samples:
            summary_lines.append("Recent sample entries: " + "; ".join(list(recent_samples)[-8:]))

        if not summary_lines:
            return "No relevant wearable metrics parsed from export."

        return "\n".join(summary_lines) + "\n(Note: Summary uses your most recent data only.)"
    except Exception as e:
        return f"Failed to parse Apple Health XML summary: {str(e)[:80]}. (Raw data will still be available for full analysis if needed.)"


def parse_date_from_text(text):
    """Try to extract a test/collection date from document text."""
    if not text:
        return None
    patterns = [
        (r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', '%m/%d/%Y'),
        (r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b', '%Y/%m/%d'),
        (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', '%B %d %Y'),
        (r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b', '%d %B %Y'),
        (r'\b(?:collected|collection|test date|date of service|dos|report date)[:\s]+(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', None),
    ]
    for pattern, fmt in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        try:
            if fmt:
                raw = match.group(0).replace('-', '/')
                for try_fmt in (fmt, fmt.replace('/', '-')):
                    try:
                        return datetime.strptime(raw, try_fmt)
                    except ValueError:
                        continue
            else:
                m, d, y = match.group(1), match.group(2), match.group(3)
                return datetime.strptime(f'{m}/{d}/{y}', '%m/%d/%Y')
        except (ValueError, IndexError):
            continue
    return None


def _doc_reference_date(doc):
    """Best estimate of when a medical test was performed."""
    if getattr(doc, 'grok_date', None):
        try:
            return datetime.strptime(doc.grok_date, '%Y-%m-%d')
        except ValueError:
            pass
    if getattr(doc, 'test_date', None):
        try:
            return datetime.strptime(doc.test_date, '%Y-%m-%d')
        except ValueError:
            pass
    if doc.extracted_text:
        parsed = parse_date_from_text(doc.extracted_text)
        if parsed:
            return parsed
    if doc.uploaded_at:
        for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                return datetime.strptime(doc.uploaded_at[:10], '%Y-%m-%d')
            except ValueError:
                continue
    return datetime.now()


def filter_recent_medical_documents(documents, reference_date=None, years=1):
    """
    Include medical tests from up to `years` before reference_date.
    Uses test_date, parsed document date, or upload date.
    """
    ref = reference_date or datetime.now()
    cutoff = ref - timedelta(days=365 * years)
    recent = []
    for doc in documents:
        test_dt = _doc_reference_date(doc)
        if test_dt >= cutoff:
            recent.append(doc)
    return recent


def combined_document_text(documents, recent_only=False, reference_date=None, max_chars=80000):
    """Merge extracted text from client documents (all by default; set recent_only=True to filter)."""
    docs = list(
        filter_recent_medical_documents(documents, reference_date) if recent_only else documents
    )
    if not docs:
        return ''

    docs.sort(key=_doc_reference_date)
    budget = max_chars or 80000
    per_doc = max(2500, budget // len(docs))

    parts = []
    for doc in docs:
        if not doc.extracted_text:
            continue
        test_dt = _doc_reference_date(doc)
        date_label = test_dt.strftime('%Y-%m-%d')
        doc_label = getattr(doc, 'grok_label', None) or doc.original_name
        excerpt = doc.extracted_text[:per_doc]
        if len(doc.extracted_text) > per_doc:
            excerpt += '\n[... document truncated for length ...]'
        parts.append(
            f'--- {doc_label} (Grok date ~{date_label}; uploaded as {doc.original_name}) ---\n{excerpt}'
        )
    return '\n\n'.join(parts)[:budget]


def describe_pdf_uploads(pdf_results):
    """Human-readable summary of processed scan PDFs for admin feedback."""
    if not pdf_results:
        return ''
    parts = []
    for pdf in pdf_results:
        name = pdf.get('original_name') or 'scan.pdf'
        size = pdf.get('file_size') or len(pdf.get('extracted_text') or '')
        chars = len((pdf.get('extracted_text') or '').strip())
        parts.append(f'{name} ({size:,} bytes, {chars:,} chars extracted)')
    return '; '.join(parts)


def process_scan_pdf_uploads(file_list, upload_dir):
    """
    Process admin-uploaded scan PDFs.
    Returns (results, errors) where results is a list of dicts and errors
    collects per-file rejections without discarding valid uploads.
    """
    if not file_list:
        return [], []

    results = []
    errors = []
    for file_storage in file_list:
        if not file_storage or not file_storage.filename:
            continue
        original = secure_filename(file_storage.filename)
        try:
            if os.path.splitext(original)[1].lower() != '.pdf':
                raise ValueError(
                    f'"{original}" is not a PDF. Only PDF scan files are supported here.'
                )

            file_storage.seek(0, os.SEEK_END)
            size = file_storage.tell()
            file_storage.seek(0)
            if size > MAX_UPLOAD_BYTES:
                raise ValueError(f'"{original}" is too large (max 16 MB).')

            os.makedirs(upload_dir, exist_ok=True)
            stored = f'{uuid.uuid4().hex}.pdf'
            path = os.path.join(upload_dir, stored)
            file_storage.save(path)
            _validate_pdf_file(path, original)
            text = extract_text(path, original, max_pages=40, max_chars=60000)
            if is_generated_report_export(text):
                from report_generator import _parse_lines
                if len(_parse_lines(text)) < 15:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    raise ValueError(
                        f'"{original}" ({size:,} bytes) is a portal download from this website — '
                        'not your scanner file. Use 1.pdf / 2.pdf / 3.pdf from your scanner folder '
                        '(18 KB–700 KB each), not "Full Scan — Jun 07" from Downloads.'
                    )
            if size < 4096 and not scan_text_has_content(text):
                try:
                    os.remove(path)
                except OSError:
                    pass
                raise ValueError(
                    f'"{original}" is only {size:,} bytes with no scan data — '
                    'likely a portal download, not a scanner PDF.'
                )
            extraction_ok = not _pdf_extraction_failed(text)
            results.append({
                'stored_filename': stored,
                'original_name': original,
                'extracted_text': text,
                'extraction_ok': extraction_ok,
                'file_size': os.path.getsize(path),
            })
            print(
                f'[Root Cause] Scan PDF OK: {original} ({size:,} bytes, '
                f'{len(text.strip()):,} chars, imaging={is_imaging_scan_format(text)})'
            )
        except ValueError as exc:
            errors.append(str(exc))
            print(f'[Root Cause] Scan PDF rejected: {exc}')

    if not results and errors:
        raise ValueError(' '.join(errors))
    return results, errors


def merge_scan_sources(pasted_text, pdf_results):
    """Combine pasted raw data and extracted PDF text into one admin-stored record."""
    parts = []
    if pasted_text and pasted_text.strip():
        parts.append(pasted_text.strip())
    for pdf in pdf_results:
        parts.append(
            f'--- SCAN PDF: {pdf["original_name"]} ---\n{pdf["extracted_text"]}'
        )
    return '\n\n'.join(parts)


def scan_pdf_extraction_issues(pdf_results):
    """Return user-facing warnings for scan PDFs that failed text extraction."""
    issues = []
    for pdf in pdf_results or []:
        text = pdf.get('extracted_text') or ''
        if _pdf_extraction_failed(text):
            issues.append(
                f'Could not read text from "{pdf.get("original_name", "scan PDF")}". '
                'Ensure XAI_API_KEY is set on Render for image PDFs, paste the scan text below, '
                'or re-upload the original Full Scan PDF (not a screenshot).'
            )
        elif is_generated_report_export(text):
            from report_generator import _parse_lines
            if len(_parse_lines(text)) < 15:
                issues.append(
                    f'"{pdf.get("original_name", "scan PDF")}" was downloaded from this website '
                    '(cover page / summary only) — it is not the original bio scan. '
                    'Upload the Full Scan PDF from your bioenergetic scanner software '
                    '(with Energetic System Performance, Sensitivities, Toxins, Metabolic Results) '
                    'or paste the raw scan text below.'
                )
        elif len(text.strip()) < 200:
            issues.append(
                f'Very little text extracted from "{pdf.get("original_name", "scan PDF")}" '
                f'({len(text.strip())} characters). The report may be incomplete.'
            )
    return issues


_SCAN_SECTION_MARKERS = (
    'energetic system performance',
    'energetic sensiti',
    'energetic nutri',
    'energetic toxins',
    'energetic hormonal',
    'metabolic test results',
    'better sleep scan',
    'hormone test results',
    'balancing remedies',
    'personalized client summary',
    'you tested with',
)

_EXPORTED_REPORT_MARKERS = (
    'executive summary',
    'markers reviewed',
    'your medical records',
    'plain english notes',
    'personalized health options',
    'original scan analysis',
    'client portal',
    'educational purposes only and is not intended to diagnose',
    'food and drug administration',
    'generated june',
    'generated january',
    'generated february',
    'generated march',
    'generated april',
    'generated may',
    'generated july',
    'generated august',
    'generated september',
    'generated october',
    'generated november',
    'generated december',
)


def _normalized_text(text):
    """Collapse whitespace so PDF line breaks do not break phrase matching."""
    return re.sub(r'\s+', ' ', (text or '').lower()).strip()


def is_imaging_scan_format(text):
    """
    True for bio-imaging scanner PDFs (CORE PRODUCT / Summary Report / D= distress).
    Distinct from Root Cause Full Scan template PDFs.
    """
    norm = _normalized_text(text)
    signals = (
        'core product',
        'summary report',
        'simular processes',
        'digestive system',
        'cross section through',
    )
    hits = sum(1 for s in signals if s in norm)
    return hits >= 2 and norm.count('d=') >= 3


def _scan_marker_count(text):
    norm = _normalized_text(text)
    return sum(1 for m in _SCAN_SECTION_MARKERS if m in norm)


def is_generated_report_export(text):
    """
    True when extracted PDF text is from our exported client report,
    not the original bioenergetic scanner Full Scan PDF.
    """
    norm = _normalized_text(text)
    if _scan_marker_count(norm) >= 2:
        return False

    export_hits = sum(1 for m in _EXPORTED_REPORT_MARKERS if m in norm)
    if export_hits >= 2:
        return True

    has_branding = 'root cause bioenergetics' in norm
    has_disclaimer = (
        'food and drug administration' in norm
        or 'not intended to diagnose' in norm
    )
    has_generated = bool(re.search(r'generated\s+[a-z]+\s+\d{1,2},?\s+\d{4}', norm))

    if has_branding and has_disclaimer:
        return True
    if has_branding and has_generated and _scan_marker_count(norm) == 0:
        return True
    if has_branding and export_hits >= 1:
        return True
    return False


def _strip_failed_pdf_wrappers(raw_text):
    """Remove placeholder blocks from failed PDF extraction."""
    text = raw_text or ''
    text = re.sub(
        r'---\s*(?:SCAN PDF|CLIENT UPLOADED SCAN):[^\n]*---\s*'
        r'\[PDF uploaded:[^\]]+\]\s*',
        '',
        text,
        flags=re.I,
    )
    return text.strip()


def is_bio_scan_document(extracted_text, original_name=''):
    """True when a client-uploaded file looks like a bioenergetic Full Scan."""
    text = extracted_text or ''
    if _pdf_extraction_failed(text):
        return False
    name_lower = (original_name or '').lower()
    if any(
        token in name_lower
        for token in ('full scan', 'bio scan', 'bioenergetic', 'hair scan', 'saliva scan')
    ):
        if len(text.strip()) >= 200:
            return True
    from scan_template import uses_template_format
    return uses_template_format(text, title=original_name)


def scan_text_has_content(raw_text):
    """Return True when raw scan text is sufficient to build a report."""
    from scan_template import uses_template_format, _find_sections, _scan_body_text
    from report_generator import _parse_lines

    body = _scan_body_text(raw_text or '')
    if _pdf_extraction_failed(body) or _pdf_extraction_failed(raw_text or ''):
        body = _strip_failed_pdf_wrappers(raw_text or '')
    if not body or len(body.strip()) < 30:
        return False
    if is_generated_report_export(body):
        return len(_parse_lines(body)) >= 15
    if uses_template_format(body):
        return bool(_find_sections(body)) or _scan_marker_count(body) >= 2
    if is_imaging_scan_format(body):
        return len(_parse_lines(body)) >= 5
    findings = _parse_lines(body)
    return len(findings) >= 5


def report_html_has_findings(html):
    """True when generated HTML includes parsed scan findings."""
    content = html or ''
    markers = (
        'body-overview', 'marker-card', 'finding-row',
        'scan-col', 'scan-remedy-card', 'top-findings',
    )
    if not any(token in content for token in markers):
        return False
    plain = re.sub(r'<[^>]+>', ' ', content)
    plain = re.sub(r'\s+', ' ', plain).strip()
    return len(plain) >= 200


def merge_client_scan_documents(pasted_text, pdf_results, documents):
    """
    Combine admin/client scan input with any Full Scan PDFs the client uploaded
    to their portal medical-documents section.
    """
    combined = merge_scan_sources(pasted_text, pdf_results)
    if scan_text_has_content(combined):
        return combined

    extra = []
    for doc in documents or []:
        if not is_bio_scan_document(doc.extracted_text, doc.original_name):
            continue
        extra.append(
            f'--- CLIENT UPLOADED SCAN: {doc.original_name} ---\n{doc.extracted_text}'
        )
    if not extra:
        return combined
    base = combined.strip()
    merged = '\n\n'.join(([base] if base else []) + extra)
    return merged


def build_pdf_results_from_paths(entries, upload_dir):
    """Re-extract text from stored scan PDF files on disk."""
    results = []
    for entry in entries or []:
        stored = entry.get('stored_filename') if isinstance(entry, dict) else entry.stored_filename
        original = (
            entry.get('original_name') if isinstance(entry, dict) else entry.original_name
        ) or stored
        path = os.path.join(upload_dir, stored)
        if not os.path.isfile(path):
            continue
        text = extract_text(path, original, max_pages=40, max_chars=60000)
        results.append({
            'stored_filename': stored,
            'original_name': original,
            'extracted_text': text,
            'extraction_ok': not _pdf_extraction_failed(text),
        })
    return results