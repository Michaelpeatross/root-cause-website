"""Public SEO routes for the bootstrapped Flask app."""


def register_public_seo_routes(app):
    """Legal pages, robots/sitemap fix, OG image. Safe to call after app load."""
    from flask import render_template, Response

    SITE = 'https://www.root-cause-test.com'

    def privacy():
        return render_template('privacy.html')

    def terms():
        return render_template('terms.html')

    def refunds():
        return render_template('refunds.html')

    def robots_txt():
        body = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /admin\n"
            "Disallow: /dashboard\n"
            "Disallow: /login\n"
            "Disallow: /register\n"
            "Disallow: /checkout/success\n"
            "Disallow: /reports/\n"
            "Disallow: /documents/\n"
            f"Sitemap: {SITE}/sitemap.xml\n"
        )
        return Response(body, mimetype='text/plain')

    def sitemap():
        pages = [
            ('/', 'weekly', '1.0'),
            ('/buy', 'monthly', '0.9'),
            ('/contact', 'monthly', '0.7'),
            ('/instructions', 'monthly', '0.6'),
            ('/health-app', 'monthly', '0.5'),
            ('/privacy', 'yearly', '0.3'),
            ('/terms', 'yearly', '0.3'),
            ('/refunds', 'yearly', '0.3'),
        ]
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for path, freq, pri in pages:
            loc = SITE if path == '/' else SITE + path
            xml.append('  <url>')
            xml.append(f'    <loc>{loc}</loc>')
            xml.append(f'    <changefreq>{freq}</changefreq>')
            xml.append(f'    <priority>{pri}</priority>')
            xml.append('  </url>')
        xml.append('</urlset>')
        return Response('\n'.join(xml), mimetype='application/xml')

    def og_scan_jpg():
        try:
            from og_image_data import OG_JPEG_B64
            import base64
            data = base64.b64decode(OG_JPEG_B64)
        except Exception:
            return Response(b'', status=404)
        return Response(data, mimetype='image/jpeg')

    routes = [
        ('/privacy', 'privacy', privacy),
        ('/terms', 'terms', terms),
        ('/refunds', 'refunds', refunds),
        ('/og-scan.jpg', 'og_scan_jpg', og_scan_jpg),
    ]
    existing = {rule.endpoint for rule in app.url_map.iter_rules()}
    for path, endpoint, view in routes:
        app.view_functions[endpoint] = view
        if endpoint not in existing:
            app.add_url_rule(path, endpoint, view)

    app.view_functions['robots_txt'] = robots_txt
    app.view_functions['sitemap'] = sitemap
    print('[Root Cause] Registered /privacy /terms /refunds + SEO robots/sitemap')
