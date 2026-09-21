"""Serve the Food Scanner OG card and rewrite social meta on public pages."""

SITE = "https://www.root-cause-test.com"
OG_IMG = f"{SITE}/static/og-food-scanner.png"
HOME_TITLE = "Root Cause Test | At-Home Wellness Scan"
HOME_DESC = (
    "At-home bioenergetic hair + saliva wellness scan. $199. "
    "Mail samples free in a regular envelope with a postage stamp, "
    "or optional $15 prepaid collection kit. Not a medical diagnosis or allergy test."
)
SCAN_TITLE = "Food Scanner | Root Cause Test"
SCAN_DESC = (
    "Free Food Scanner from Root Cause Test. Scan a barcode, nutrition label, "
    "or plate photo for educational wellness calorie and macro estimates. "
    "Not medical advice."
)


def _fallback_png():
    """Always-valid 1200x630 PNG so social crawlers never get a 404."""
    import io
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1200, 630
    im = Image.new("RGB", (W, H), "#0b3d2a")
    draw = ImageDraw.Draw(im)
    draw.rectangle((720, 0, W, H), fill="#f4ead8")
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except Exception:
        title_font = small = brand = ImageFont.load_default()
    draw.text((64, 56), "Root Cause", fill="#f4ead8", font=brand)
    draw.text((64, 108), "WELLNESS, ROOTED IN REALITY.", fill="#c5ddd4", font=small)
    draw.text((64, 200), "FREE", fill="#f4ead8", font=title_font)
    draw.text((64, 275), "FOOD SCANNER", fill="#f4ead8", font=title_font)
    draw.text((64, 380), "Barcode  •  Label  •  Plate photo", fill="#d7efe8", font=small)
    draw.text((64, 520), "SCAN. UNDERSTAND. NOURISH.", fill="#c5ddd4", font=small)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _as_png(raw):
    import io
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return raw, "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            if im.size != (1200, 630):
                im = im.resize((1200, 630))
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            return buf.getvalue(), "image/png"
        except Exception:
            return raw, "image/jpeg"
    return None


def _png_bytes():
    import base64
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("og-food-scanner.png", "og-food-scanner.jpg"):
        disk = os.path.join(here, "static", name)
        try:
            if os.path.isfile(disk) and os.path.getsize(disk) > 1000:
                with open(disk, "rb") as fh:
                    converted = _as_png(fh.read())
                if converted:
                    return converted
        except Exception:
            pass
    for mod_name, attr in (("og_food_image", "OG_FOOD_JPG_B64"), ("og_image_data", "OG_JPEG_B64")):
        try:
            mod = __import__(mod_name)
            raw = base64.b64decode("".join(getattr(mod, attr).split()))
            converted = _as_png(raw)
            if converted:
                return converted
        except Exception:
            pass
    try:
        return _fallback_png(), "image/png"
    except Exception:
        return b"", "application/octet-stream"


def register_og_card(app):
    from flask import Response, request
    import re

    def og_food_scanner_png():
        data, mime = _png_bytes()
        if not data:
            return Response(b"", status=404)
        resp = Response(data, mimetype=mime or "image/png")
        resp.headers["Cache-Control"] = "public, max-age=3600"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    orig_static = app.view_functions.get("static")

    def static_with_og(filename):
        if filename in ("og-food-scanner.png", "og-scan.jpg"):
            return og_food_scanner_png()
        if orig_static is not None:
            return orig_static(filename)
        return Response(b"", status=404)

    app.view_functions["static"] = static_with_og
    app.view_functions["og_food_scanner_png"] = og_food_scanner_png
    app.view_functions["og_scan_jpg"] = og_food_scanner_png
    app.view_functions["og_scan_jpg_card"] = og_food_scanner_png

    for path, endpoint in (
        ("/static/og-food-scanner.png", "og_food_scanner_png"),
        ("/og-scan.jpg", "og_scan_jpg_card"),
        ("/og-scan.jpg", "og_scan_jpg"),
    ):
        try:
            app.add_url_rule(path, endpoint, og_food_scanner_png)
        except Exception:
            pass

    @app.before_request
    def _og_card_before():
        path = request.path or ""
        if path in ("/static/og-food-scanner.png", "/og-scan.jpg", "/static/og-scan.jpg"):
            return og_food_scanner_png()
        return None

    @app.after_request
    def _og_card_touch(response):
        try:
            ctype = response.headers.get("Content-Type", "")
            if "text/html" not in ctype:
                return response
            html = response.get_data(as_text=True)
            if not html or "<head" not in html:
                return response
            path = request.path or "/"
            canon = SITE + ("/" if path == "/" else path)
            html = html.replace("https://www.root-cause-test.com/og-scan.jpg", OG_IMG)
            html = html.replace("http://www.root-cause-test.com/og-scan.jpg", OG_IMG)
            html = html.replace('content="/og-scan.jpg"', f'content="{OG_IMG}"')
            html = html.replace('content="/static/og-scan.jpg"', f'content="{OG_IMG}"')
            html = re.sub(
                r'<meta property="og:image" content="[^"]*"\s*/?>',
                f'<meta property="og:image" content="{OG_IMG}">',
                html,
                flags=re.I,
            )
            html = re.sub(
                r'<meta name="twitter:image" content="[^"]*"\s*/?>',
                f'<meta name="twitter:image" content="{OG_IMG}">',
                html,
                flags=re.I,
            )
            html = re.sub(
                r'<meta property="og:url" content="[^"]*"\s*/?>',
                f'<meta property="og:url" content="{canon}">',
                html,
                flags=re.I,
            )
            html = re.sub(
                r'<meta property="og:type" content="[^"]*"\s*/?>',
                '<meta property="og:type" content="website">',
                html,
                flags=re.I,
            )
            html = re.sub(
                r'<meta name="twitter:card" content="[^"]*"\s*/?>',
                '<meta name="twitter:card" content="summary_large_image">',
                html,
                flags=re.I,
            )
            inject = ""
            if 'property="og:image"' not in html:
                inject += f'<meta property="og:image" content="{OG_IMG}">'
            if 'property="og:image:type"' not in html:
                inject += '<meta property="og:image:type" content="image/png">'
            if 'property="og:image:width"' not in html:
                inject += '<meta property="og:image:width" content="1200">'
            if 'property="og:image:height"' not in html:
                inject += '<meta property="og:image:height" content="630">'
            if 'name="twitter:image"' not in html:
                inject += f'<meta name="twitter:image" content="{OG_IMG}">'
            if 'name="twitter:card"' not in html:
                inject += '<meta name="twitter:card" content="summary_large_image">'
            if 'property="og:type"' not in html:
                inject += '<meta property="og:type" content="website">'
            if 'property="og:url"' not in html:
                inject += f'<meta property="og:url" content="{canon}">'

            if path == "/":
                title, desc = HOME_TITLE, HOME_DESC
            elif path == "/scan-food":
                title, desc = SCAN_TITLE, SCAN_DESC
            else:
                title, desc = None, None
            if title:
                html = re.sub(
                    r'<meta property="og:title" content="[^"]*"\s*/?>',
                    f'<meta property="og:title" content="{title}">',
                    html,
                    flags=re.I,
                )
                html = re.sub(
                    r'<meta name="twitter:title" content="[^"]*"\s*/?>',
                    f'<meta name="twitter:title" content="{title}">',
                    html,
                    flags=re.I,
                )
                html = re.sub(r"<title>[^<]*</title>", f"<title>{title}</title>", html, count=1, flags=re.I)
                if 'property="og:title"' not in html:
                    inject += f'<meta property="og:title" content="{title}">'
                if 'name="twitter:title"' not in html:
                    inject += f'<meta name="twitter:title" content="{title}">'
            if desc:
                html = re.sub(
                    r'<meta property="og:description" content="[^"]*"\s*/?>',
                    f'<meta property="og:description" content="{desc}">',
                    html,
                    flags=re.I,
                )
                html = re.sub(
                    r'<meta name="twitter:description" content="[^"]*"\s*/?>',
                    f'<meta name="twitter:description" content="{desc}">',
                    html,
                    flags=re.I,
                )
                html = re.sub(
                    r'<meta name="description" content="[^"]*"\s*/?>',
                    f'<meta name="description" content="{desc}">',
                    html,
                    flags=re.I,
                )
                if 'property="og:description"' not in html:
                    inject += f'<meta property="og:description" content="{desc}">'
                if 'name="twitter:description"' not in html:
                    inject += f'<meta name="twitter:description" content="{desc}">'
            if inject and "</head>" in html:
                html = html.replace("</head>", inject + "</head>", 1)
            response.set_data(html)
        except Exception as exc:
            print("[Root Cause] OG card after_request skipped:", exc)
        return response

    print("[Root Cause] Registered Food Scanner OG card at /static/og-food-scanner.png")
