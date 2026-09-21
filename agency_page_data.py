"""Compressed ApexForge landing HTML (zlib+base64). Generated; do not edit by hand."""
import base64
import zlib

from agency_b64_0 import PART as _p0
from agency_b64_1 import PART as _p1
from agency_b64_2 import PART as _p2
from agency_b64_3 import PART as _p3

_B64 = _p0 + _p1 + _p2 + _p3


def agency_html() -> str:
    return zlib.decompress(base64.b64decode(_B64)).decode("utf-8")
