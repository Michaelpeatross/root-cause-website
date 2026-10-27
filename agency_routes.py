"""ApexForge marketing-agency landing — isolated from Root Cause scan checkout."""

import os


def _decode_agency_html():
    """Decode compressed landing HTML; repair known one-char base64 corruption if present."""
    import base64
    import zlib
    from agency_page_data import _B64

    raw = "".join(_B64)
    # Transit typo in initial publish: HYOdEqmJn should be HYOfEqmJn
    if "HYOdEqmJn" in raw:
        raw = raw.replace("HYOdEqmJn", "HYOfEqmJn")
    return zlib.decompress(base64.b64decode(raw)).decode("utf-8")


_BUSINESS_NAV = (
    '<span style="display:flex;align-items:center;gap:1.1rem;">'
    '<a href="/business" style="font-size:0.875rem;color:var(--text-muted);">Business</a>'
)
_BUSINESS_FOOTER = (
    ' · <a href="/business" style="color:var(--text-dim);text-decoration:underline;'
    'text-underline-offset:2px;">Business services</a>'
    ' · <a href="/ai-transformation" style="color:var(--text-dim);text-decoration:underline;'
    'text-underline-offset:2px;">AI Transformation</a>'
)


def _add_business_links(html):
    """Add a small /business nav + footer link to the ApexForge agency page (idempotent)."""
    if 'href="/business"' in html:
        return html
    import re

    html = re.sub(
        r'(<a class="nav-cta"[^>]*>[^<]*</a>)',
        lambda m: _BUSINESS_NAV + m.group(1) + "</span>",
        html,
        count=1,
    )
    html = html.replace(
        "Separate from Root Cause Test.</p>",
        "Separate from Root Cause Test." + _BUSINESS_FOOTER + "</p>",
        1,
    )
    return html


def register_agency_routes(app):
    """Serve /agency, /apexforge, /business, /ai-transformation, plus the Foam Insulation
    offer page at /foam and /spray-foam. Does not touch Stripe/scan checkout."""
    from flask import Response, request

    def _load_html():
        path = os.path.join(app.root_path, "templates", "agency.html")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        try:
            return _decode_agency_html()
        except Exception as exc:
            raise FileNotFoundError(f"agency.html missing and decode failed: {exc}") from exc

    def _agency_page():
        try:
            html = _load_html()
        except Exception as exc:
            print(f"[ApexForge] agency page unavailable: {exc}")
            return Response(
                "<!DOCTYPE html><html><body><h1>ApexForge</h1>"
                "<p>Landing page temporarily unavailable.</p>"
                '<p><a href="https://www.root-cause-test.com/">Root Cause</a></p>'
                "</body></html>",
                status=503,
                mimetype="text/html",
            )
        return Response(_add_business_links(html), mimetype="text/html; charset=utf-8")

    def _static_agency_page(filename, title):
        def _view():
            path = os.path.join(app.root_path, "templates", filename)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    html = fh.read()
            except Exception as exc:
                print(f"[ApexForge] {filename} unavailable: {exc}")
                return Response(
                    f"<!DOCTYPE html><html><body><h1>ApexForge {title}</h1>"
                    "<p>Page temporarily unavailable.</p>"
                    '<p><a href="/agency">ApexForge</a></p>'
                    "</body></html>",
                    status=503,
                    mimetype="text/html",
                )
            return Response(html, mimetype="text/html; charset=utf-8")

        return _view

    _business_page = _static_agency_page("business.html", "Business")
    _ai_page = _static_agency_page("ai_transformation.html", "AI Transformation")

    def _k12_page():
        """K-12 tuition scholarship page: coming soon, no donations, noindex."""
        path = os.path.join(app.root_path, "templates", "k12_scholarships.html")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                html = fh.read()
            status = 200
        except Exception as exc:
            print(f"[K12] k12_scholarships.html unavailable: {exc}")
            html = ("<!DOCTYPE html><html><head><meta name=\"robots\" content=\"noindex\"></head>"
                    "<body><h1>K-12 Tuition Scholarships</h1><p>Coming soon. Not accepting donations yet.</p>"
                    "</body></html>")
            status = 503
        resp = Response(html, status=status, mimetype="text/html")
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp

    def _k12_og_image():
        import base64
        from k12_og_image import PNG_B64
        resp = Response(base64.b64decode("".join(PNG_B64)), mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    def _house_plans_page():
        """House plans / drafting offer page (separate look; not ApexForge, not Root Cause)."""
        path = os.path.join(app.root_path, "templates", "house_plans.html")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                html = fh.read()
            status = 200
        except Exception as exc:
            print(f"[HousePlans] house_plans.html unavailable: {exc}")
            html = ("<!DOCTYPE html><html><body><h1>Custom House Plans</h1>"
                    "<p>Page temporarily unavailable. Email "
                    '<a href="mailto:michaelpeatross@gmail.com?bcc=michaelpeatross%40gmail.com'
                    '&amp;subject=House%20plans">michaelpeatross@gmail.com</a>.</p>'
                    "</body></html>")
            status = 503
        resp = Response(html, status=status, mimetype="text/html")
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    def _house_plans_og_image():
        import base64
        from house_plans_og_image import PNG_B64
        resp = Response(base64.b64decode("".join(PNG_B64)), mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    def _foam_page():
        """Foam Insulation, LLC spray foam offer page (separate business; no Root Cause chrome)."""
        path = os.path.join(app.root_path, "templates", "foam.html")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                html = fh.read()
        except Exception as exc:
            print(f"[Foam] foam.html unavailable: {exc}")
            return Response(
                "<!DOCTYPE html><html><body><h1>Foam Insulation, LLC</h1>"
                "<p>Spray foam insulation in Lafayette &amp; Acadiana. "
                'Call <a href="tel:+13378493132">(337) 849-3132</a> for a free quote.</p>'
                "</body></html>",
                status=503,
                mimetype="text/html",
            )
        return Response(html, mimetype="text/html; charset=utf-8")

    routes = [
        ("/agency", "apexforge_agency", _agency_page),
        ("/apexforge", "apexforge_alias", _agency_page),
        ("/business", "apexforge_business", _business_page),
        ("/ai-transformation", "apexforge_ai_transformation", _ai_page),
        ("/foam", "foam_insulation_offer", _foam_page),
        ("/spray-foam", "foam_insulation_spray_foam_alias", _foam_page),
        ("/k12-scholarships", "k12_scholarships_coming_soon", _k12_page),
        ("/k12-og.png", "k12_scholarships_og_image", _k12_og_image),
        ("/house-plans", "house_plans_offer", _house_plans_page),
        ("/house-plans-og.png", "house_plans_og_image", _house_plans_og_image),
    ]
    existing = {rule.endpoint for rule in app.url_map.iter_rules()}
    for path, endpoint, view in routes:
        app.view_functions[endpoint] = view
        if endpoint not in existing:
            app.add_url_rule(path, endpoint, view, methods=["GET", "HEAD"])

    # Root Cause seo_routes injects footer/nav into all HTML. Skip that for ApexForge pages.
    agency_paths = {
        "/agency", "/apexforge", "/business", "/ai-transformation",
        "/foam", "/spray-foam", "/k12-scholarships", "/house-plans",
    }

    def _wrap_seo_processors():
        wrapped = 0
        for _key, funcs in list(getattr(app, "after_request_funcs", {}).items()):
            for idx, fn in enumerate(list(funcs)):
                name = getattr(fn, "__name__", "")
                if name != "_seo_html_touch":
                    continue
                if getattr(fn, "_apexforge_wrapped", False):
                    continue

                def _guard(response, _orig=fn):
                    try:
                        path = (request.path or "/").rstrip("/") or "/"
                        if path in agency_paths or path.startswith("/agency"):
                            return response
                    except Exception:
                        pass
                    return _orig(response)

                _guard.__name__ = "_seo_html_touch"
                _guard._apexforge_wrapped = True
                funcs[idx] = _guard
                wrapped += 1
        return wrapped

    n = _wrap_seo_processors()
    print(
        "[ApexForge] Registered /agency, /apexforge, /business, /ai-transformation, "
        "/foam, /spray-foam, /k12-scholarships, /house-plans "
        f"(marketing agency landing; SEO chrome wrappers={n})"
    )
