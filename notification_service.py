"""Email and SMS notifications for clients and admin."""
import base64
import os
import re
import urllib.parse
import urllib.request

from email_service import send_plain_email


def _twilio_configured():
    return all([
        os.environ.get('TWILIO_ACCOUNT_SID'),
        os.environ.get('TWILIO_AUTH_TOKEN'),
        os.environ.get('TWILIO_FROM_NUMBER'),
    ])


def _normalize_phone(number):
    if not number:
        return ''
    digits = re.sub(r'\D', '', number.strip())
    if len(digits) == 10:
        return f'+1{digits}'
    if len(digits) == 11 and digits.startswith('1'):
        return f'+{digits}'
    if number.strip().startswith('+'):
        return '+' + digits
    return f'+{digits}' if digits else ''


def send_sms(to_number, message):
    """Send SMS via Twilio. Returns (success, message)."""
    to_num = _normalize_phone(to_number)
    if not to_num:
        return False, 'No phone number on file.'
    if not _twilio_configured():
        return False, 'SMS not configured (set TWILIO_* environment variables).'

    sid = os.environ['TWILIO_ACCOUNT_SID']
    token = os.environ['TWILIO_AUTH_TOKEN']
    from_num = os.environ['TWILIO_FROM_NUMBER']

    body = urllib.parse.urlencode({
        'To': to_num,
        'From': from_num,
        'Body': message[:1500],
    }).encode('utf-8')

    url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
    req = urllib.request.Request(url, data=body, method='POST')
    creds = base64.b64encode(f'{sid}:{token}'.encode()).decode()
    req.add_header('Authorization', f'Basic {creds}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
        return True, f'SMS sent to {to_num}.'
    except Exception as exc:
        return False, f'SMS failed: {exc}'


def notify_client_analysis_update(client_email, client_name, client_phone, report_title, plain_text, pdf_bytes=None):
    """Email and SMS client with updated Grok analysis."""
    site = os.environ.get('SITE_URL', 'https://root-cause-website.onrender.com')
    subject = f'Updated Health Analysis — {report_title}'
    body = (
        f'Hi {client_name},\n\n'
        f'Your updated Root Cause health analysis is ready.\n\n'
        f'{plain_text[:2500]}\n\n'
        f'Log in to your portal for the full report and PDF:\n{site}/login\n\n'
        f'— Root Cause Bioenergetics'
    )
    email_ok, email_msg = send_plain_email(
        client_email, subject, body, pdf_bytes, f'{report_title}.pdf'
    )
    sms_ok, sms_msg = send_sms(
        client_phone,
        f'Root Cause: Your updated health analysis for "{report_title}" is ready. '
        f'Check your email and client portal.',
    )
    return email_ok, email_msg, sms_ok, sms_msg


def notify_admin_analysis_request(client_name, client_email, report_title):
    """Email and SMS admin when client requests updated analysis."""
    admin_email = os.environ.get('ADMIN_EMAIL', 'michaelpeatross@gmail.com')
    admin_phone = os.environ.get('ADMIN_PHONE', '')
    site = os.environ.get('SITE_URL', 'https://root-cause-website.onrender.com')

    subject = f'Client Requested Updated Analysis — {client_name}'
    body = (
        f'Client {client_name} ({client_email}) requested an updated Grok analysis.\n\n'
        f'Report: {report_title}\n'
        f'A new analysis has been generated and sent to the client.\n\n'
        f'Review in admin panel: {site}/admin'
    )
    email_ok, email_msg = send_plain_email(admin_email, subject, body)
    sms_ok, sms_msg = send_sms(
        admin_phone,
        f'Root Cause Admin: {client_name} requested updated analysis for "{report_title}". '
        f'New analysis sent to client.',
    )
    return email_ok, email_msg, sms_ok, sms_msg