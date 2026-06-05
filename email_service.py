"""Send report emails to clients via SMTP."""
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _smtp_configured():
    return bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_FROM'))


def send_report_email(to_email, subject, text_body, pdf_bytes=None, pdf_filename='report.pdf'):
    """
    Email plain-text summary and optional PDF attachment.
    Returns (success: bool, message: str).
    """
    if not _smtp_configured():
        return False, 'Email not configured (set SMTP_HOST and SMTP_FROM environment variables).'

    from_addr = os.environ['SMTP_FROM']
    host = os.environ['SMTP_HOST']
    port = int(os.environ.get('SMTP_PORT', '587'))
    user = os.environ.get('SMTP_USER', from_addr)
    password = os.environ.get('SMTP_PASSWORD', '')

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_email
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))

    if pdf_bytes:
        attachment = MIMEApplication(pdf_bytes, _subtype='pdf')
        attachment.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
        msg.attach(attachment)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true':
                server.starttls()
            if password:
                server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        return True, f'Report emailed to {to_email}.'
    except Exception as exc:
        return False, f'Email failed: {exc}'