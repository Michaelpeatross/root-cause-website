"""Stripe Checkout — cards, Apple Pay, Google Pay, and Link."""
import os
from urllib.parse import urlparse

import stripe

stripe.api_key = (os.environ.get('STRIPE_SECRET_KEY') or '').strip()

PRODUCTS = {
    'single': {
        'name': 'Root Cause Bioenergetic Scan',
        'description': 'One personalized hair + saliva bioenergetic analysis',
        'amount': 19900,
    },
    'bundle_4': {
        'name': 'Root Cause 4-Scan Bundle',
        'description': 'Four bioenergetic scans — best value for ongoing monitoring',
        'amount': 49900,
    },
}

DEFAULT_PRICE_CENTS = 19900

DEFAULT_CHECKOUT_DOMAINS = (
    'www.root-cause-test.com',
    'root-cause-test.com',
)


def stripe_configured():
    return bool(stripe.api_key and stripe.api_key.startswith('sk_'))


def _checkout_domains(site_url=None):
    domains = set(DEFAULT_CHECKOUT_DOMAINS)
    if site_url:
        host = urlparse(site_url).hostname
        if host:
            domains.add(host)
    return sorted(domains)


def register_apple_pay_domains(site_url=None):
    """
    Register site domains with Stripe so Apple Pay / Google Pay appear on Checkout.
    Required for www and apex domain (Apple treats www as separate).
    """
    if not stripe_configured():
        return []

    registered = []
    for domain in _checkout_domains(site_url):
        try:
            stripe.PaymentMethodDomain.create(domain_name=domain)
            registered.append(domain)
            print(f'[Root Cause] Registered payment domain for Apple Pay: {domain}')
        except stripe.error.StripeError as exc:
            msg = str(getattr(exc, 'user_message', None) or exc)
            lower = msg.lower()
            if 'already' in lower and ('exist' in lower or 'registered' in lower):
                registered.append(domain)
            else:
                print(f'[Root Cause] Payment domain {domain}: {msg}')
    return registered


def create_checkout_session(site_url, customer_email=None, coupon_code=None, product_key='single'):
    """
    Create Stripe Checkout Session with wallets (Apple Pay, Google Pay, Link).
    Returns (session_url, error_message).
    """
    if not stripe_configured():
        return None, (
            'Online card checkout is not active yet. Add STRIPE_SECRET_KEY in Render '
            'Environment (Dashboard → root-cause-website → Environment). Use your '
            'secret key from dashboard.stripe.com — it starts with sk_live_ or sk_test_.'
        )

    register_apple_pay_domains(site_url)

    product = PRODUCTS.get(product_key, PRODUCTS['single'])
    amount = product['amount']
    if product_key == 'single' and (coupon_code or '').lower() == 'welcome50':
        amount = 19900

    base = site_url.rstrip('/')
    success_url = f'{base}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}'
    cancel_url = f'{base}/dashboard' if customer_email else f'{base}/'

    session_params = {
        'mode': 'payment',
        'automatic_payment_methods': {'enabled': True},
        'line_items': [{
            'price_data': {
                'currency': 'usd',
                'unit_amount': amount,
                'product_data': {
                    'name': product['name'],
                    'description': product['description'],
                },
            },
            'quantity': 1,
        }],
        'success_url': success_url,
        'cancel_url': cancel_url,
        'billing_address_collection': 'auto',
        'phone_number_collection': {'enabled': True},
        'metadata': {'product': product_key},
    }
    if customer_email:
        session_params['customer_email'] = customer_email

    try:
        session = stripe.checkout.Session.create(**session_params)
        return session.url, None
    except stripe.error.StripeError as exc:
        err = str(getattr(exc, 'user_message', None) or exc)
        print(f'[Root Cause] Stripe checkout error: {err}')
        fallback = {
            'mode': 'payment',
            'payment_method_types': ['card', 'link'],
            'line_items': session_params['line_items'],
            'success_url': session_params['success_url'],
            'cancel_url': session_params['cancel_url'],
            'billing_address_collection': 'auto',
            'phone_number_collection': {'enabled': True},
            'metadata': session_params['metadata'],
        }
        if customer_email:
            fallback['customer_email'] = customer_email
        try:
            session = stripe.checkout.Session.create(**fallback)
            return session.url, None
        except stripe.error.StripeError as retry_exc:
            return None, str(getattr(retry_exc, 'user_message', None) or retry_exc)
def retrieve_checkout_session(session_id):
    """Retrieve a checkout session by ID for post-purchase processing (e.g. thank you notifications).
    Returns the session object or None on error.
    """
    if not stripe_configured() or not session_id:
        return None
    try:
        return stripe.checkout.Session.retrieve(
            session_id,
            expand=['customer_details', 'payment_intent']
        )
    except Exception as exc:
        print(f'[Root Cause] Failed to retrieve checkout session {session_id}: {exc}')
        return None
