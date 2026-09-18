"""Serve the Food Scanner OG card and rewrite social meta on public pages."""

SITE = "https://www.root-cause-test.com"
OG_IMG = f"{SITE}/static/og-food-scanner.png"
HOME_TITLE = "Root Cause Test | At-Home Wellness Scan"
HOME_DESC = (
    "At-home bioenergetic hair + saliva wellness scan with a clear report "
    "and supplement ideas. $199. Not a medical diagnosis or allergy test."
)
SCAN_TITLE = "Food Scanner | Root Cause Test"
SCAN_DESC = (
    "Free Food Scanner from Root Cause Test. Scan a barcode, nutrition label, "
    "or plate photo for educational wellness calorie and macro estimates. "
    "Not medical advice."
)


def _png_bytes():
    import base64
    import io
    import os

    disk = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "og-food-scanner.png")
    try:
        if os.path.isfile(disk) and os.path.getsize(disk) > 1000:
            with open(disk, "rb") as fh:
                data = fh.read()
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                return data
    except Exception:
        pass
    raw = b""
    try:
        from og_food_image import OG_FOOD_JPG_B64
        raw = base64.b64decode(OG_FOOD_JPG_B64)
    except Exception:
        raw = b""
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return raw
    if raw[:3] == b"\xff\xd8\xff":
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
        except Exception:
            return raw
    return raw


def register_og_card(app):
    from flask import Response, request
    import re

    def og_food_scanner_png():
        data = _png_bytes()
        if not data:
            return Response(b"", status=404)
        mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        resp = Response(data, mimetype=mime)
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    orig_static = app.view_functions.get("static")

    def static_with_og(filename):
        if filename == "og-food-scanner.png":
            return og_food_scanner_png()
        if orig_static is not None:
            return orig_static(filename)
        return Response(b"", status=404)

    app.view_functions["static"] = static_with_og
    app.view_functions["og_food_scanner_png"] = og_food_scanner_png
    app.view_functions["og_scan_jpg_card"] = og_food_scanner_png
    try:
        app.add_url_rule("/static/og-food-scanner.png", "og_food_scanner_png", og_food_scanner_png)
    except Exception:
        pass
    try:
        app.add_url_rule("/og-scan.jpg", "og_scan_jpg_card", og_food_scanner_png)
    except Exception:
        pass

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
            html = html.replace('content="/og-scan.jpg"', f'content="{OG_IMG}"')
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
                if path == "/scan-food":
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
