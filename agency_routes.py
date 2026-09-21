"""ApexForge marketing-agency landing — isolated from Root Cause scan checkout."""

import os


def register_agency_routes(app):
    """Serve /agency and /apexforge from templates/agency.html. Does not touch Stripe/scan."""
    from flask import Response

    def _agency_page():
        path = os.path.join(app.root_path, "templates", "agency.html")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                html = fh.read()
        except OSError as exc:
            print(f"[ApexForge] agency.html missing: {exc}")
            return Response(
                "<!DOCTYPE html><html><body><h1>ApexForge</h1>"
                "<p>Landing page temporarily unavailable.</p>"
                '<p><a href="https://www.root-cause-test.com/">Root Cause</a></p>'
                "</body></html>",
                status=503,
                mimetype="text/html",
            )
        return Response(html, mimetype="text/html; charset=utf-8")

    routes = [
        ("/agency", "apexforge_agency", _agency_page),
        ("/apexforge", "apexforge_alias", _agency_page),
    ]
    existing = {rule.endpoint for rule in app.url_map.iter_rules()}
    for path, endpoint, view in routes:
        app.view_functions[endpoint] = view
        if endpoint not in existing:
            app.add_url_rule(path, endpoint, view, methods=["GET", "HEAD"])

    print("[ApexForge] Registered /agency and /apexforge (marketing agency landing)")
