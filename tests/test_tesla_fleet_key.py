"""Tesla Fleet well-known public-key route must return the PEM byte-for-byte."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
flask = pytest.importorskip("flask")

PEM_PATH = os.path.join(ROOT, "well-known", "appspecific", "com.tesla.3p.public-key.pem")
ROUTE = "/.well-known/appspecific/com.tesla.3p.public-key.pem"


def test_tesla_fleet_public_key_route():
    assert os.path.isfile(PEM_PATH)
    expected = open(PEM_PATH, "rb").read()
    assert expected.startswith(b"-----BEGIN PUBLIC KEY-----")
    assert expected.endswith(b"-----END PUBLIC KEY-----\n")

    app = flask.Flask(__name__)
    from tesla_fleet_key import register_tesla_fleet_key_routes

    register_tesla_fleet_key_routes(app)
    client = app.test_client()
    resp = client.get(ROUTE)
    assert resp.status_code == 200
    assert resp.data == expected
    ctype = (resp.headers.get("Content-Type") or "").lower()
    assert ctype.startswith("text/plain") or "application/x-pem-file" in ctype
