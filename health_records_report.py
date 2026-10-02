"""Put every uploaded health record into the client report."""
import os
import re
from html import escape

_STUB_MARKERS = (
    'recent trends will be summarized',
    'text extraction unavailable',
    'extraction failed',
    'review with your practitioner',
)

_FLAG = re.compile(
    r'\b(high|low|abnormal|critical|positive|negative|elevated|deficient|'
    r'out of range|borderline|reactive|detected)\b|(?:^|\s)[HL](?:\s|$)',
    re.I,
)
_NUMBER = re.compile(r'\d')
_HEADER = re.compile(
    r'^(page|patient|dob|date of birth|account|specimen|collected|printed|'
    r'clia|ordering|provider|address|phone|fax|mrn|accession)\b',
    re.I,
)
_ANALYTE = re.compile(
    r'\b(tsh|t3|t4|a1c|hba1c|glucose|vitamin d|25-oh|ferritin|iron|b12|'
    r'folate|ldl|hdl|triglycer|cholesterol|hemoglobin|hematocrit|wbc|rbc|'
    r'platelets|crp|hs-crp|cortisol|insulin|sodium|potassium|creatinine|'
    r'egfr|alt|ast|bilirubin|magnesium|calcium|testosterone|estradiol|'
    r'progesterone|dhea|homocysteine|neutrophil|lymphocyte)\b',
    re.I,
)
_WEARABLE = re.compile(
    r'avg=|HeartRate|RestingHeartRate|StepCount|Sleep|HeartRateVariability|'
    r'ActiveEnergy|HRV',
    re.I,
)


def text_is_stub(text):
    lower = (text or '').lower()
    if len(lower.strip()) < 40:
        return True
    return any(marker in lower for marker in _STUB_MARKERS)


def refresh_document_text(doc, documents_dir):
    """Re-read a saved file when the stored text is only a placeholder."""
    text = getattr(doc, 'extracted_text', None) or ''
    filename = getattr(doc, 'stored_filename', None) or ''
    if not documents_dir or not filename or not text_is_stub(text):
        return False
    path = os.path.join(documents_dir, filename)
    if not os.path.isfile(path):
        return False
    try:
        from document_service import extract_text
        fresh = extract_text(
            path,
            getattr(doc, 'original_name', None) or filename,
            max_pages=40,
            max_chars=120000,
            allow_grok_vision=False,
        )
    except Exception:
        return False
    if not fresh or text_is_stub(fresh) or len(fresh) <= len(text):
        return False
    doc.extracted_text = fresh
    return True


def notable_lines(text, limit=80):
    """Lab flags, known analytes, and wearable summaries. Skip page headers."""
    found = []
    seen = set()
    for raw in (text or '').splitlines():
        line = ' '.join(raw.split())
        if len(line) < 6 or len(line) > 220:
            continue
        key = line.lower()
        if key in seen or _HEADER.match(line):
            continue
        keep = bool(_WEARABLE.search(line))
        if not keep and _NUMBER.search(line) and (_FLAG.search(line) or _ANALYTE.search(line)):
            keep = True
        if not keep:
            continue
        seen.add(key)
        found.append(line)
        if len(found) >= limit:
            break
    return found


def _is_scan_file(text, name):
    try:
        from document_service import is_bio_scan_document
        return is_bio_scan_document(text, name)
    except Exception:
        return False


def health_records_html(documents, client_name='Client'):
    """Client-facing block. Every uploaded record is named, even if unreadable."""
    first = escape(((client_name or 'Client').split() or ['Client'])[0])
    docs = list(documents or [])
    if not docs:
        return (
            '<h3>Uploaded health records</h3>'
            '<p>%s, no labs, blood tests, or wearable files are on this account yet. '
            'Add them in the portal and they are included in this analysis.</p>'
            % first
        )

    rows = []
    unread = 0
    used = 0
    for doc in docs:
        label = (
            getattr(doc, 'grok_label', None)
            or getattr(doc, 'original_name', None)
            or 'Health record'
        )
        when = (
            getattr(doc, 'grok_date', None)
            or getattr(doc, 'test_date', None)
            or getattr(doc, 'uploaded_at', None)
            or ''
        )
        text = getattr(doc, 'extracted_text', None) or ''
        name = getattr(doc, 'original_name', None) or ''
        if _is_scan_file(text, name):
            detail = 'Earlier bioenergetic scan. Compared in the organ chart above, not repeated here.'
            used += 1
        else:
            lines = notable_lines(text)
            if lines:
                detail = '; '.join(lines)
                used += 1
            elif text_is_stub(text):
                detail = 'File is saved. No readable lab or wearable numbers could be extracted.'
                unread += 1
            else:
                detail = 'Read. No flagged lab lines or wearable numbers stood out.'
                used += 1
        rows.append(
            '<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (escape(str(label)[:120]), escape(str(when)[:32]), escape(detail))
        )

    return (
        '<h3>Uploaded health records</h3>'
        '<p>%s, this analysis includes all %s health file%s on the account. '
        '%s had readable results. %s could not be read as text.</p>'
        '<table class="organ-chart"><tr>'
        '<th>Record</th><th>Date</th><th>What was included</th></tr>%s</table>'
        '<p>These lines come from your uploads. They are not a diagnosis and not a full copy of each page.</p>'
        % (
            first,
            len(docs),
            '' if len(docs) == 1 else 's',
            used,
            unread,
            ''.join(rows),
        )
    )
