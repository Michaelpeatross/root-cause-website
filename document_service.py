"""Handle client medical document uploads and text extraction."""
import os
import re
import uuid
from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp',
    '.doc', '.docx', '.heic', '.heif',
}
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
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
            f'"{original}" type not allowed. Use PDF, images (PNG/JPG/WEBP/GIF), TXT, or DOC/DOCX.'
        )

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError('File too large (max 16 MB).')

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


def _extract_pdf_text(file_path, max_pages=40, max_chars=60000):
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
            text = '\n'.join(
                doc[i].get_text() for i in range(min(len(doc), max_pages))
            ).strip()
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

    return ''


def extract_text(file_path, original_name, *, max_pages=30, max_chars=20000):
    """Extract readable text from an uploaded document."""
    ext = os.path.splitext(original_name or file_path)[1].lower()

    if ext == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()[:max_chars]

    if ext == '.pdf':
        text = _extract_pdf_text(file_path, max_pages=max_pages, max_chars=max_chars)
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

    return f'[Document uploaded: {original_name}]'


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


def process_scan_pdf_uploads(file_list, upload_dir):
    """
    Process admin-uploaded scan PDFs.
    Returns list of dicts: stored_filename, original_name, extracted_text.
    """
    if not file_list:
        return []

    results = []
    for file_storage in file_list:
        if not file_storage or not file_storage.filename:
            continue
        original = secure_filename(file_storage.filename)
        if os.path.splitext(original)[1].lower() != '.pdf':
            raise ValueError(f'"{original}" is not a PDF. Only PDF scan files are supported here.')

        file_storage.seek(0, os.SEEK_END)
        size = file_storage.tell()
        file_storage.seek(0)
        if size > MAX_UPLOAD_BYTES:
            raise ValueError(f'"{original}" is too large (max 16 MB).')

        os.makedirs(upload_dir, exist_ok=True)
        stored = f'{uuid.uuid4().hex}.pdf'
        path = os.path.join(upload_dir, stored)
        file_storage.save(path)
        text = extract_text(path, original, max_pages=40, max_chars=60000)
        results.append({
            'stored_filename': stored,
            'original_name': original,
            'extracted_text': text,
            'extraction_ok': not _pdf_extraction_failed(text),
        })
    return results


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
                'Paste the scan text below or re-upload the PDF.'
            )
        elif len(text.strip()) < 200:
            issues.append(
                f'Very little text extracted from "{pdf.get("original_name", "scan PDF")}" '
                f'({len(text.strip())} characters). The report may be incomplete.'
            )
    return issues