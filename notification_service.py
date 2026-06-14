"""Email and SMS notifications for clients and admin."""
import base64
import json
import os
import re
import urllib.parse
import urllib.request

from email_service import send_plain_email


def _textbelt_key():
    """Cheapest reliable option for low-volume SMS (textbelt.com). ~0.3¢/text vs Twilio ~0.75-1¢."""
    return (os.environ.get('TEXTBELT_API_KEY') or '').strip()


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
    """Send SMS. Prefers Textbelt (cheapest for low volume) if TEXTBELT_API_KEY is set,
    otherwise falls back to Twilio. Returns (success: bool, message: str).
    """
    to_num = _normalize_phone(to_number)
    if not to_num:
        return False, 'No phone number on file.'

    textbelt_key = _textbelt_key()
    if textbelt_key:
        # Textbelt: one of the cheapest production SMS options (~$3 per 1,000 texts, simple REST)
        try:
            data = urllib.parse.urlencode({
                'phone': to_num,
                'message': (message or '')[:1500],
                'key': textbelt_key,
            }).encode('utf-8')
            req = urllib.request.Request('https://textbelt.com/text', data=data, method='POST')
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            if result.get('success'):
                return True, f'SMS sent to {to_num} (Textbelt).'
            else:
                err = result.get('error') or result.get('message') or 'Unknown Textbelt error'
                return False, f'Textbelt error: {err}'
        except Exception as exc:
            return False, f'Textbelt failed: {exc}'

    if not _twilio_configured():
        return False, 'SMS not configured (set TEXTBELT_API_KEY for cheapest, or TWILIO_* vars).'

    # Twilio fallback (existing implementation)
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


def deliver_report_to_client(
    client_email, client_name, client_phone, report_title, plain_text,
    pdf_bytes=None, send_email=True, send_sms=True,
):
    """Send report to client via selected channels. Returns list of status messages."""
    site = os.environ.get('SITE_URL', 'https://root-cause-website.onrender.com')
    results = []

    if send_email:
        subject = f'Your Root Cause Report: {report_title}'
        body = (
            f'Hi {client_name},\n\n'
            f'Your personalized Root Cause bioenergetic report is ready.\n\n'
            f'{plain_text[:2500]}\n\n'
            f'View your full report and download the PDF in your client portal:\n'
            f'{site}/login\n\n'
            f'— Root Cause Bioenergetics'
        )
        ok, msg = send_plain_email(
            client_email, subject, body, pdf_bytes, f'{report_title}.pdf'
        )
        results.append(('email', ok, msg))
    else:
        results.append(('email', None, 'Email not selected.'))

    if send_sms:
        ok, msg = send_sms(
            client_phone,
            f'Root Cause: Your report "{report_title}" is ready. '
            f'Log in to your portal: {site}/login',
        )
        results.append(('sms', ok, msg))
    else:
        results.append(('sms', None, 'Text not selected.'))

    return results


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
    results = deliver_report_to_client(
        client_email, client_name, client_phone, report_title, plain_text,
        pdf_bytes, send_email=True, send_sms=True,
    )
    email_ok = next((r[1] for r in results if r[0] == 'email'), False)
    email_msg = next((r[2] for r in results if r[0] == 'email'), '')
    sms_ok = next((r[1] for r in results if r[0] == 'sms'), False)
    sms_msg = next((r[2] for r in results if r[0] == 'sms'), '')
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
def send_purchase_thank_you(customer_email, customer_name, customer_phone, product_name, site_url):
    """Send automated thank-you email (and SMS if phone provided) for a completed purchase.
    Called after successful Stripe checkout.
    """
    if not customer_email:
        return
    name = customer_name or (customer_email.split('@')[0] if customer_email else 'Customer')

    # Email
    try:
        subject = f"Thank you for your {product_name} purchase!"
        body = (
            f"Hi {name},\n\n"
            f"Thank you for purchasing the {product_name}!\n\n"
            f"Your payment has been successfully processed.\n\n"
            f"Next steps:\n"
            f"- Log in or create your free account using {customer_email} at {site_url}/login\n"
            f"- Review collection instructions: {site_url}/instructions\n"
            f"- Your practitioner will prepare and publish your personalized bioenergetic report.\n\n"
            f"If you have any questions, just reply to this email.\n\n"
            f"- Root Cause Bioenergetics\n{site_url}"
        )
        send_plain_email(customer_email, subject, body)
    except Exception as exc:
        print(f"[Root Cause] Purchase thank-you email failed for {customer_email}: {exc}")

    # SMS (if we have a phone from checkout collection)
    if customer_phone:
        try:
            sms_msg = (
                f"Root Cause: Thank you for your {product_name} purchase! "
                f"Check email at {customer_email} for details. "
                f"Login at {site_url}/login to proceed with your scan collection."
            )
            send_sms(customer_phone, sms_msg)
        except Exception as exc:
            print(f"[Root Cause] Purchase thank-you SMS failed for {customer_phone}: {exc}")


def send_welcome_to_root_cause(customer_email, customer_name, customer_phone, site_url):
    """Send a friendly welcome email (and SMS if phone) when a new client account is created."""
    if not customer_email:
        return
    name = customer_name or (customer_email.split('@')[0] if customer_email else 'there')

    # Welcome Email
    try:
        subject = "Welcome to Root Cause Bioenergetics!"
        body = (
            f"Hi {name},\n\n"
            f"Welcome to Root Cause! We're thrilled you've joined us on your wellness journey.\n\n"
            f"With Root Cause Bioenergetic Hair + Saliva Analysis, we help uncover hidden patterns "
            f"in sensitivities, toxins, metabolic function, and more — all from the comfort of home.\n\n"
            f"Next steps:\n"
            f"- If you haven't purchased yet, visit {site_url}/buy to get started.\n"
            f"- Read the easy collection instructions: {site_url}/instructions\n"
            f"- Create or log into your portal at {site_url}/login\n"
            f"- Once your sample is processed, your personalized report will appear here.\n\n"
            f"Questions? Just reply to this email — we're here to help.\n\n"
            f"Here's to discovering your root cause,\n"
            f"— The Root Cause Team\n{site_url}"
        )
        send_plain_email(customer_email, subject, body)
    except Exception as exc:
        print(f"[Root Cause] Welcome email failed for {customer_email}: {exc}")

    # SMS welcome (if phone on file)
    if customer_phone:
        try:
            sms_msg = (
                f"Welcome to Root Cause, {name}! Your account is ready. "
                f"Check your email for next steps or login at {site_url}/login. "
                f"We're excited to help uncover your root causes."
            )
            send_sms(customer_phone, sms_msg)
        except Exception as exc:
            print(f"[Root Cause] Welcome SMS failed for {customer_phone}: {exc}")
