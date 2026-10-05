"""Serve Tesla Fleet API third-party public key at the required well-known path."""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PEM_PATH = os.path.join(
    _HERE, "well-known", "appspecific", "com.tesla.3p.public-key.pem"
)
_ROUTE = "/.well-known/appspecific/com.tesla.3p.public-key.pem"


def register_tesla_fleet_key_routes(app):
    """Public, unauthenticated PEM for Tesla third-party app pairing."""
    from flask import Response

    def tesla_3p_public_key():
        if not os.path.isfile(_PEM_PATH):
            return Response("Not Found\n", status=404, mimetype="text/plain")
        with open(_PEM_PATH, "rb") as f:
            data = f.read()
        resp = Response(data, status=200, mimetype="text/plain")
        resp.headers["Cache-Control"] = "public, max-age=300"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    app.add_url_rule(
        _ROUTE,
        endpoint="tesla_3p_public_key",
        view_func=tesla_3p_public_key,
        methods=["GET", "HEAD"],
        strict_slashes=False,
    )
