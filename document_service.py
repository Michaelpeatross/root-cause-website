"""Handle client medical document uploads and text extraction."""
import os
import re
import uuid
from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.png', '.jpg', '.jpeg', '.doc', '.docx'}
MAX_UPLOAD_BYTES = 16 * 1024 * 1024


def allowed_file(filename):
    ext = os.path.splitext(filename or '')[1].lower()
    return ext in ALLOWED_EXTENSIONS


def save_upload(file_storage, upload_dir):
    """Save uploaded file; returns (stored_name, original_name) or raises ValueError."""
    if not file_storage or not file_storage.filename:
        raise ValueError('No file selected.')

    original = secure_filename(file_storage.filename)
    if not allowed_file(original):
        raise ValueError('File type not allowed. Use PDF, TXT, DOC, DOCX, or images.')

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


def extract_text(file_path, original_name):
    """Extract readable text from an uploaded document."""
    ext = os.path.splitext(original_name or file_path)[1].lower()

    if ext == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()[:20000]

    if ext == '.pdf':
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            parts = []
            for page in reader.pages[:30]:
                text = page.extract_text() or ''
                parts.append(text)
            return '\n'.join(parts)[:20000]
        except Exception:
            return f'[PDF uploaded: {original_name} — text extraction unavailable]'

    if ext == '.docx':
        try:
            from docx import Document
            doc = Document(file_path)
            return '\n'.join(p.text for p in doc.paragraphs if p.text)[:20000]
        except Exception:
            return f'[Word document uploaded: {original_name}]'

    if ext in {'.png', '.jpg', '.jpeg'}:
        return f'[Medical image uploaded: {original_name} — review with your practitioner]'

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


def combined_document_text(documents, recent_only=True, reference_date=None):
    """Merge extracted text from client documents (optionally last 12 months only)."""
    docs = filter_recent_medical_documents(documents, reference_date) if recent_only else documents
    parts = []
    for doc in docs:
        if doc.extracted_text:
            test_dt = _doc_reference_date(doc)
            date_label = test_dt.strftime('%Y-%m-%d')
            parts.append(
                f'--- {doc.original_name} (test date ~{date_label}) ---\n{doc.extracted_text}'
            )
    return '\n\n'.join(parts)[:40000]


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
        text = extract_text(path, original)
        results.append({
            'stored_filename': stored,
            'original_name': original,
            'extracted_text': text,
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