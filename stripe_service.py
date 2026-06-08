"""Stripe Checkout — cards, Apple Pay, and Link (lowest-friction options)."""
import os

import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

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


def stripe_configured():
    return bool(stripe.api_key and stripe.api_key.startswith('sk_'))


def create_checkout_session(site_url, customer_email=None, coupon_code=None, product_key='single'):
    """
    Create Stripe Checkout Session.
    Supports credit/debit cards, Apple Pay, Google Pay, and Stripe Link.
    Stripe's blended rate (~2.9% + 30¢) is among the lowest for integrated checkout.
    Returns (session_url, error_message).
    """
    if not stripe_configured():
        return None, (
            'Online card checkout is not active yet. Add STRIPE_SECRET_KEY in Render '
            'Environment (Dashboard → root-cause-website → Environment). Use your '
            'secret key from dashboard.stripe.com — it starts with sk_live_ or sk_test_. '
            'Or use Email Order on the buy page.'
        )

    product = PRODUCTS.get(product_key, PRODUCTS['single'])
    amount = product['amount']
    if product_key == 'single' and (coupon_code or '').lower() == 'welcome50':
        amount = 19900

    success_url = f'{site_url.rstrip("/")}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}'
    cancel_url = f'{site_url.rstrip("/")}/dashboard' if customer_email else f'{site_url.rstrip("/")}/buy'

    try:
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
            'allow_promotion_codes': True,
            'billing_address_collection': 'auto',
            'phone_number_collection': {'enabled': True},
            'metadata': {'product': product_key},
        }
        if customer_email:
            session_params['customer_email'] = customer_email

        session = stripe.checkout.Session.create(**session_params)
        return session.url, None
    except stripe.error.StripeError as exc:
        return None, str(exc.user_message if hasattr(exc, 'user_message') else exc)