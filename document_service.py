"""Handle client medical document uploads and text extraction."""
import os
import uuid

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


def combined_document_text(documents):
    """Merge extracted text from a list of ClientDocument model instances."""
    parts = []
    for doc in documents:
        if doc.extracted_text:
            parts.append(f'--- {doc.original_name} ---\n{doc.extracted_text}')
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