"""Stripe Checkout — cards, Apple Pay, and Link (lowest-friction options)."""
import os

import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

PRODUCT_NAME = 'Root Cause Bioenergetic Hair + Saliva Analysis'
DEFAULT_PRICE_CENTS = 19900  # $199.00
DISCOUNT_PRICE_CENTS = 19900  # welcome50 keeps $199


def stripe_configured():
    return bool(stripe.api_key and stripe.api_key.startswith('sk_'))


def create_checkout_session(site_url, customer_email=None, coupon_code=None):
    """
    Create Stripe Checkout Session.
    Supports credit/debit cards, Apple Pay, Google Pay, and Stripe Link.
    Stripe's blended rate (~2.9% + 30¢) is among the lowest for integrated checkout.
    Returns (session_url, error_message).
    """
    if not stripe_configured():
        return None, 'Stripe is not configured. Set STRIPE_SECRET_KEY on the server.'

    amount = DISCOUNT_PRICE_CENTS if (coupon_code or '').lower() == 'welcome50' else DEFAULT_PRICE_CENTS

    success_url = f'{site_url.rstrip("/")}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}'
    cancel_url = f'{site_url.rstrip("/")}/buy'

    try:
        session_params = {
            'mode': 'payment',
            'payment_method_types': ['card', 'link'],
            'line_items': [{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': amount,
                    'product_data': {
                        'name': PRODUCT_NAME,
                        'description': 'Personalized bioenergetic analysis with supplement and lab guidance',
                    },
                },
                'quantity': 1,
            }],
            'success_url': success_url,
            'cancel_url': cancel_url,
            'allow_promotion_codes': True,
            'billing_address_collection': 'auto',
            'phone_number_collection': {'enabled': True},
            'metadata': {'product': 'bioenergetic_analysis'},
        }
        if customer_email:
            session_params['customer_email'] = customer_email

        session = stripe.checkout.Session.create(**session_params)
        return session.url, None
    except stripe.error.StripeError as exc:
        return None, str(exc.user_message if hasattr(exc, 'user_message') else exc)