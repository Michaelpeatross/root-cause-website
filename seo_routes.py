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

    FOOTER = (
        '<footer class="site-footer">'
        '<div class="footer-inner"><strong>Root Cause Test</strong> \u00b7 ROOTCAUSE LLC'
        '<nav aria-label="Footer">'
        '<a href="/contact">Contact</a> '
        '<a href="/privacy">Privacy</a> '
        '<a href="/terms">Terms</a> '
        '<a href="/refunds">Refunds</a> '
        '<a href="/health-app">Health App</a> '
        '<a href="/login">Login</a>'
        '</nav>'
        '<p class="fine">Wellness information only. This at-home bioenergetic hair and saliva scan '
        'is not a medical diagnosis, not an allergy test, not a DNA test, and not intended to detect '
        'or treat disease. It does not replace care from a licensed clinician. Questions: '
        '<a href="mailto:test@root-cause-test.com">test@root-cause-test.com</a></p>'
        '</div></footer>'
        '<style>.site-footer{background:#0b3d2a;color:rgba(255,255,255,.88);margin-top:3rem;padding:2rem 1.5rem 2.5rem}'
        '.site-footer .footer-inner{max-width:1100px;margin:0 auto}.site-footer a{color:#d7efe8}'
        '.site-footer nav{display:flex;flex-wrap:wrap;gap:.75rem 1.25rem;margin:.75rem 0 1rem}'
        '.site-footer .fine{font-size:.82rem;color:rgba(255,255,255,.7);line-height:1.55;max-width:720px}'
        '.compare-table{width:100%;border-collapse:collapse;font-size:.95rem}'
        '.compare-table th,.compare-table td{border:1px solid #dfe6e9;padding:.7rem .8rem;text-align:left}'
        '.compare-table th{background:#0b3d2a;color:#fff}.compare-table tr:nth-child(even) td{background:#f3faf7}'
        '.step-grid,.include-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem}'
        '.faq details{background:#fff;border-radius:12px;padding:1rem 1.15rem;margin:0 0 .75rem;box-shadow:0 4px 24px rgba(11,61,42,.08)}'
        '.faq summary{cursor:pointer;font-weight:600;color:#0b3d2a}</style>'
    )

    NOINDEX_PREFIXES = (
        '/login', '/register', '/checkout/success', '/admin',
        '/dashboard', '/reports', '/documents',
    )

    @app.after_request
    def _seo_html_touch(response):
        try:
            ctype = response.headers.get('Content-Type', '')
            if 'text/html' not in ctype:
                return response
            html = response.get_data(as_text=True)
            if not html or '<head' not in html:
                return response
            from flask import request
            path = request.path or '/'
            canon = SITE + ('/' if path == '/' else path)
            noindex = path == '/checkout/success' or any(
                path == p or path.startswith(p + '/') for p in NOINDEX_PREFIXES
            ) or response.status_code == 404
            robots = 'noindex, nofollow' if noindex else 'index, follow'
            extra = (
                f'<link rel="canonical" href="{canon}">'
                f'<meta name="robots" content="{robots}">'
                f'<meta property="og:url" content="{canon}">'
                f'<meta property="og:image" content="{SITE}/og-scan.jpg">'
                f'<meta name="twitter:card" content="summary_large_image">'
                f'<meta name="twitter:image" content="{SITE}/og-scan.jpg">'
            )
            if path == '/':
                html = html.replace(
                    'Root Cause Test: Bioenergetic scanning combined with Grok AI analysis of your wearable health data, blood work, and medical records. Personalized reports and recommendations.',
                    'At-home bioenergetic hair + saliva wellness scan with a clear report and supplement ideas. $199. Not a medical diagnosis or allergy test.',
                )
                html = html.replace(
                    'Upload your Apple Watch, Fitbit, blood work and medical records. Grok analyzes everything for deep health insights.',
                    'At-home bioenergetic hair + saliva wellness scan with a clear report and supplement ideas. $199. Not a medical diagnosis or allergy test.',
                )
            if '</head>' in html and 'rel="canonical"' not in html:
                html = html.replace('</head>', extra + '</head>', 1)
            if 'site-footer' not in html and '</body>' in html:
                html = html.replace('</body>', FOOTER + '</body>', 1)
            if response.status_code == 404 and 'noindex' not in html:
                html = html.replace('<head>', '<head><meta name="robots" content="noindex, nofollow">', 1)
            response.set_data(html)
        except Exception as exc:
            print(f'[Root Cause] SEO after_request skipped: {exc}')
        return response

    print('[Root Cause] Registered /privacy /terms /refunds + SEO robots/sitemap')
