"""Public SEO routes for the bootstrapped Flask app."""


def register_public_seo_routes(app):
    """Legal pages, robots/sitemap fix, OG image. Safe to call after app load."""
    from flask import render_template, Response

    SITE = 'https://www.root-cause-test.com'

    # One title + meta description per indexable public page.
    # Keyword map: docs/seo-keywords.md. Keep wellness framing — no medical claims.
    PAGE_SEO = {
        '/': (
            'At-Home Bioenergetic Hair & Saliva Scan – $199 | Root Cause Test',
            'Order a $199 at-home bioenergetic hair and saliva wellness scan. Collect samples at home, '
            'mail them free with a stamp, and get a prioritized wellness report. Not a diagnosis.',
        ),
        '/buy': (
            'Order the $199 At-Home Bioenergetic Scan | Root Cause Test',
            'Order your $199 bioenergetic hair and saliva wellness scan online. Secure Stripe checkout. '
            'Mail samples free with a stamp, add a $15 prepaid kit, or overnight for speed.',
        ),
        '/how-it-works': (
            'How the At-Home Hair & Saliva Scan Works | Root Cause Test',
            'Order, collect hair and saliva at home, mail your samples, and read your wellness report '
            '7–14 days after they arrive. Free stamp mail, optional $15 kit, overnight for speed.',
        ),
        '/scan-food': (
            'Free Food Scanner: Barcode, Label & Plate Photo | Root Cause Test',
            'Free online Food Scanner. Scan a barcode, nutrition label, or plate photo for a 1–100 food '
            'processing score plus calorie and macro estimates. No app or account needed.',
        ),
        '/sample-report': (
            'Sample Bioenergetic Wellness Report | Root Cause Test',
            'See a sample bioenergetic wellness report from a $199 hair and saliva scan: top 3 priorities, '
            'Health Scores, and body-system cards. Placeholder data. Not a diagnosis.',
        ),
        '/blog': (
            'Bioenergetic Scan Guides | Root Cause Test',
            'Plain-language guides to the at-home bioenergetic hair and saliva wellness scan: what it is, '
            'what it is not, and how it compares with allergy testing and HTMA.',
        ),
        '/blog/what-is-bioenergetic-hair-saliva-scan': (
            'What Is a Bioenergetic Hair & Saliva Scan? | Root Cause Test',
            'What an at-home bioenergetic hair and saliva wellness scan is, what it is not, and how it '
            'differs from allergy testing and HTMA. Plain-language guide. Not medical advice.',
        ),
        '/blog/bioenergetic-vs-food-allergy-test': (
            'Bioenergetic Scan vs Food Allergy Test | Root Cause Test',
            'Bioenergetic hair and saliva wellness scan vs clinical food allergy testing, side by side. '
            'A wellness scan does not diagnose or rule out food allergy. See the real limits.',
        ),
        '/health-app': (
            'Upload Health Records & Wearable Data | Root Cause Test',
            'Optional: upload Apple Health, Fitbit, or Garmin exports and lab PDFs you downloaded for extra '
            'wellness context next to your $199 scan. We never ask for portal passwords.',
        ),
        '/export-records': (
            'How to Export MyChart, Labcorp & Quest Records | Root Cause Test',
            'Step-by-step: download your own MyChart, Labcorp, Quest, and Apple Health files, then upload '
            'them for optional wellness context. We never ask for portal passwords.',
        ),
        '/contact': (
            'Contact Root Cause Test | Questions About the $199 Scan',
            'Questions about the $199 at-home hair and saliva wellness scan, shipping, or the Free Food '
            'Scanner? Text or email Root Cause Test and get a quick answer.',
        ),
        '/privacy': (
            'Privacy Policy | Root Cause Test',
            'How Root Cause Test collects, uses, and protects account, scan, Food Scanner, and optional '
            'health-record data. We do not sell your personal information.',
        ),
        '/terms': (
            'Terms of Use | Root Cause Test',
            'Terms of use for Root Cause Test, the $199 at-home bioenergetic hair and saliva wellness scan '
            'and Free Food Scanner. Wellness information only, not medical care.',
        ),
        '/refunds': (
            'Refund Policy | Root Cause Test',
            'Refund policy for the $199 Root Cause Test hair and saliva wellness scan: cancellations before '
            'you mail samples, and what happens once processing starts.',
        ),
    }

    # Duplicate URLs that should consolidate to one canonical page.
    CANONICAL_ALIASES = {'/food-scanner': '/scan-food'}

    # Breadcrumb trail (name, path) for BreadcrumbList JSON-LD.
    BREADCRUMBS = {
        '/buy': [('Order', '/buy')],
        '/how-it-works': [('How it works', '/how-it-works')],
        '/scan-food': [('Food Scanner', '/scan-food')],
        '/sample-report': [('Sample report', '/sample-report')],
        '/blog': [('Guides', '/blog')],
        '/blog/what-is-bioenergetic-hair-saliva-scan': [
            ('Guides', '/blog'),
            ('What is a bioenergetic hair and saliva scan?', '/blog/what-is-bioenergetic-hair-saliva-scan'),
        ],
        '/blog/bioenergetic-vs-food-allergy-test': [
            ('Guides', '/blog'),
            ('Bioenergetic scan vs food allergy test', '/blog/bioenergetic-vs-food-allergy-test'),
        ],
        '/export-records': [('Export your records', '/export-records')],
        '/health-app': [('Health records', '/health-app')],
    }

    def privacy():
        return render_template('privacy.html')

    def terms():
        return render_template('terms.html')

    def refunds():
        return render_template('refunds.html')

    def sample_report():
        sample_html = ''
        try:
            from sample_report_builder import build_sample_report_html
            sample_html = build_sample_report_html() or ''
            # The page already has its own H1; keep one H1 per page.
            import re as _re_h1
            sample_html = _re_h1.sub(
                r'<h1(\s[^>]*)?>(.*?)</h1>',
                lambda m: '<h2%s>%s</h2>' % (m.group(1) or '', m.group(2)),
                sample_html,
                flags=_re_h1.I | _re_h1.S,
            )
        except Exception as exc:
            print('[Root Cause] sample report build failed: %s' % exc)
            sample_html = (
                '<p>The sample template could not be generated just now. '
                'A Root Cause wellness report uses Health Scores, top priorities, '
                'and body-system cards. It is informational only — not a diagnosis '
                'or allergy test.</p>'
            )
        return render_template('sample_report.html', sample_html=sample_html)

    def how_it_works():
        return render_template('how_it_works.html')

    def blog_what_is_scan():
        return render_template('blog/what_is_scan.html')

    def blog_vs_allergy():
        return render_template('blog/vs_allergy.html')

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
            "Disallow: /instructions\n"
            "Disallow: /api/\n"
            "Disallow: /account/\n"
            f"Sitemap: {SITE}/sitemap.xml\n"
        )
        return Response(body, mimetype='text/plain')

    def sitemap():
        pages = [
            ('/', 'weekly', '1.0'),
            ('/buy', 'monthly', '0.9'),
            ('/contact', 'monthly', '0.7'),
            ('/how-it-works', 'monthly', '0.8'),
            ('/sample-report', 'monthly', '0.7'),
            ('/scan-food', 'weekly', '0.8'),
            ('/blog', 'monthly', '0.6'),
            ('/blog/what-is-bioenergetic-hair-saliva-scan', 'monthly', '0.7'),
            ('/blog/bioenergetic-vs-food-allergy-test', 'monthly', '0.7'),
            ('/health-app', 'monthly', '0.5'),
            ('/export-records', 'monthly', '0.5'),
            ('/privacy', 'yearly', '0.3'),
            ('/terms', 'yearly', '0.3'),
            ('/refunds', 'yearly', '0.3'),
        ]
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for path, freq, pri in pages:
            loc = SITE + path
            xml.append('  <url>')
            xml.append(f'    <loc>{loc}</loc>')
            xml.append(f'    <changefreq>{freq}</changefreq>')
            xml.append(f'    <priority>{pri}</priority>')
            xml.append('  </url>')
        xml.append('</urlset>')
        return Response('\n'.join(xml), mimetype='application/xml')

    OG_IMG = f'{SITE}/static/og-food-scanner.png'

    def og_scan_jpg():
        try:
            from og_card import _png_bytes
            data, mime = _png_bytes()
            if data:
                return Response(data, mimetype=mime or 'image/png')
        except Exception:
            pass
        try:
            from og_food_image import OG_FOOD_JPG_B64
            import base64
            data = base64.b64decode(OG_FOOD_JPG_B64)
            return Response(data, mimetype='image/jpeg')
        except Exception:
            return Response(b'', status=404)

    routes = [
        ('/privacy', 'privacy', privacy),
        ('/terms', 'terms', terms),
        ('/refunds', 'refunds', refunds),
        ('/sample-report', 'sample_report', sample_report),
        ('/how-it-works', 'how_it_works', how_it_works),
        ('/blog/what-is-bioenergetic-hair-saliva-scan', 'blog_what_is_scan', blog_what_is_scan),
        ('/blog/bioenergetic-vs-food-allergy-test', 'blog_vs_allergy', blog_vs_allergy),
        ('/og-scan.jpg', 'og_scan_jpg', og_scan_jpg),
    ]
    existing = {rule.endpoint for rule in app.url_map.iter_rules()}
    for path, endpoint, view in routes:
        app.view_functions[endpoint] = view
        if endpoint not in existing:
            app.add_url_rule(path, endpoint, view)

    app.view_functions['robots_txt'] = robots_txt
    app.view_functions['sitemap'] = sitemap

    def buy_page():
        """Public $199 landing page with shipping copy. Checkout stays POST /create-checkout-session."""
        return render_template('buy.html')

    app.view_functions['buy'] = buy_page

    FOOTER = (
        '<footer class="site-footer">'
        '<div class="footer-inner">'
        '<div class="footer-brand"><strong>Root Cause Test</strong><span>ROOTCAUSE LLC</span></div>'
        '<div class="footer-cols">'
        '<div class="footer-col"><h4>Product</h4>'
        '<a href="/how-it-works">How it works</a>'
        '<a href="/sample-report">Sample report</a>'
        '<a href="/buy">Order — $199</a></div>'
        '<div class="footer-col"><h4>Tools</h4>'
        '<a href="/scan-food">Food Scanner</a>'
        '<a href="/health-app">Health records</a>'
        '<a href="/export-records">Export records</a>'
        '<a href="/blog">Guides</a></div>'
        '<div class="footer-col"><h4>Company</h4>'
        '<a href="/contact">Contact</a>'
        '<a href="/privacy">Privacy</a>'
        '<a href="/terms">Terms</a>'
        '<a href="/refunds">Refunds</a>'
        '<a href="/login">Log in</a></div>'
        '</div>'
        '<p class="fine">Wellness information only. This at-home bioenergetic hair and saliva scan '
        'is not a medical diagnosis, not an allergy test, not a DNA test, and not intended to detect '
        'or treat disease. It does not replace care from a licensed clinician. Questions: '
        '<a href="mailto:test@root-cause-test.com">test@root-cause-test.com</a></p>'
        '</div></footer>'
        '<style>'
        '.site-footer{background:#0b3d2a;color:rgba(255,255,255,.88);margin-top:3rem;padding:2.5rem 1.5rem 2.75rem}'
        '.site-footer .footer-inner{max-width:1100px;margin:0 auto}'
        '.site-footer a{color:#d7efe8;text-decoration:none}'
        '.site-footer a:hover{color:#fff;text-decoration:underline}'
        '.footer-brand{display:flex;flex-wrap:wrap;gap:.5rem 1rem;align-items:baseline;margin-bottom:1.25rem}'
        '.footer-brand strong{font-size:1.05rem;color:#fff}'
        '.footer-brand span{font-size:.85rem;opacity:.75}'
        '.footer-cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1.5rem;margin:0 0 1.5rem}'
        '.footer-col{display:flex;flex-direction:column;gap:.45rem}'
        '.footer-col h4{margin:0 0 .35rem;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,.55);font-weight:600}'
        '.site-footer .fine{font-size:.82rem;color:rgba(255,255,255,.7);line-height:1.55;max-width:720px;margin:0}'
        '@media(max-width:700px){.footer-cols{grid-template-columns:1fr 1fr}}'
        '@media(max-width:420px){.footer-cols{grid-template-columns:1fr}}'
        '.compare-table{width:100%;border-collapse:collapse;font-size:.95rem}'
        '.compare-table th,.compare-table td{border:1px solid #dfe6e9;padding:.7rem .8rem;text-align:left}'
        '.compare-table th{background:#0b3d2a;color:#fff}.compare-table tr:nth-child(even) td{background:#f3faf7}'
        '.step-grid,.include-grid{display:grid;grid-template-columns:1fr;gap:1rem}'
        '@media(min-width:760px){.step-grid,.include-grid{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}}'
        '.faq details{background:#fff;border-radius:12px;padding:1rem 1.15rem;margin:0 0 .75rem;box-shadow:0 4px 24px rgba(11,61,42,.08)}'
        '.faq summary{cursor:pointer;font-weight:600;color:#0b3d2a}'
        '.section-title{text-align:center;font-family:"Playfair Display",serif;color:#0b3d2a;margin:2.25rem 0 1.25rem}'
        '.hero-actions{display:flex;flex-wrap:wrap;gap:.75rem;justify-content:center;align-items:center}'
        '.hero .btn-ghost{background:rgba(255,255,255,.12);border:1.5px solid rgba(255,255,255,.85);color:#fff}'
        '.hero .btn-ghost:hover{background:rgba(255,255,255,.22);color:#fff;text-decoration:none}'
        'body{padding-bottom:72px}'
        '@media(max-width:720px){'
        '#grok-label,#grok-bubble-label{display:none!important}'
        '#grok-float{bottom:12px;right:12px}'
        '#grok-panel{width:min(360px,calc(100vw - 24px));max-height:58vh}'
        'body{padding-bottom:96px}'
        '.container,.card,form{padding-bottom:12px}'
        '.btn-primary,.btn-secondary{margin-bottom:8px}'
        '}'
        '</style>'
    )

    NOINDEX_PREFIXES = (
        '/login', '/register', '/checkout/success', '/admin',
        '/dashboard', '/reports', '/documents', '/nutrition',
        '/instructions',
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
            # /food-scanner is an alias of /scan-food — one canonical URL.
            canon_path = CANONICAL_ALIASES.get(path, path)
            canon = SITE + ('/' if canon_path == '/' else canon_path)
            noindex = path == '/checkout/success' or any(
                path == p or path.startswith(p + '/') for p in NOINDEX_PREFIXES
            ) or response.status_code == 404
            robots = 'noindex, nofollow' if noindex else 'index, follow'
            seo_title, seo_desc = PAGE_SEO.get(canon_path, (None, None))
            html = html.replace('https://www.root-cause-test.com/og-scan.jpg', OG_IMG)
            html = html.replace('http://www.root-cause-test.com/og-scan.jpg', OG_IMG)
            import re as _re_seo
            extra = (
                f'<link rel="canonical" href="{canon}">'
                f'<meta name="robots" content="{robots}">'
                f'<meta property="og:url" content="{canon}">'
                f'<meta property="og:image" content="{SITE}/static/og-food-scanner.png">'
                f'<meta name="twitter:card" content="summary_large_image">'
                f'<meta name="twitter:image" content="{SITE}/static/og-food-scanner.png">'
            )
            if seo_title and seo_desc and not noindex:
                html = _re_seo.sub(
                    r'<title>[^<]*</title>',
                    f'<title>{seo_title}</title>',
                    html,
                    count=1,
                    flags=_re_seo.I,
                )
                html = _re_seo.sub(
                    r'<meta name="description" content="[^"]*"\s*/?>',
                    f'<meta name="description" content="{seo_desc}">',
                    html,
                    flags=_re_seo.I,
                )
                html = _re_seo.sub(
                    r'<meta property="og:title" content="[^"]*"\s*/?>',
                    f'<meta property="og:title" content="{seo_title}">',
                    html,
                    flags=_re_seo.I,
                )
                html = _re_seo.sub(
                    r'<meta property="og:description" content="[^"]*"\s*/?>',
                    f'<meta property="og:description" content="{seo_desc}">',
                    html,
                    flags=_re_seo.I,
                )
                html = _re_seo.sub(
                    r'<meta name="twitter:description" content="[^"]*"\s*/?>',
                    f'<meta name="twitter:description" content="{seo_desc}">',
                    html,
                    flags=_re_seo.I,
                )
                # Avoid duplicate metas: only inject when the template omitted them.
                if 'name="description"' not in html.lower():
                    extra += f'<meta name="description" content="{seo_desc}">'
                if 'property="og:description"' not in html.lower():
                    extra += f'<meta property="og:description" content="{seo_desc}">'
                if 'property="og:title"' not in html.lower():
                    extra += f'<meta property="og:title" content="{seo_title}">'
            crumb_trail = BREADCRUMBS.get(canon_path)
            if crumb_trail and 'BreadcrumbList' not in html and not noindex:
                import json as _json
                items = [{
                    '@type': 'ListItem',
                    'position': 1,
                    'name': 'Home',
                    'item': SITE + '/',
                }]
                for i, (name, cpath) in enumerate(crumb_trail, start=2):
                    items.append({
                        '@type': 'ListItem',
                        'position': i,
                        'name': name,
                        'item': SITE + cpath,
                    })
                crumb_json = _json.dumps({
                    '@context': 'https://schema.org',
                    '@type': 'BreadcrumbList',
                    'itemListElement': items,
                }, ensure_ascii=True)
                extra += f'<script type="application/ld+json">{crumb_json}</script>'
            if path in ('/login', '/register', '/buy', '/contact', '/checkout/success'):
                html = html.replace('<body>', '<body class="rc-form-page">', 1)
                extra += '<style>.rc-form-page #grok-label,.rc-form-page #grok-bubble-label{display:none!important}</style>'
            if '</head>' in html and 'rel="canonical"' not in html:
                html = html.replace('</head>', extra + '</head>', 1)
            # Prefer clear product language site-wide
            html = html.replace('>Get Analysis</a>', '>Order</a>')
            html = html.replace('Get Your Analysis — $199', 'Order your scan — $199')
            html = html.replace('Get Your Analysis', 'Order your scan')
            html = html.replace('>Scan Food</a>', '>Food Scanner</a>')
            html = html.replace('>Buy $199</a>', '>Order — $199</a>')
            if 'href="/scan-food"' not in html:
                NAV = (
                    '<a href="/how-it-works">How it works</a> '
                    '<a href="/scan-food">Food Scanner</a> '
                    '<a href="/sample-report">Sample report</a> '
                )
                if 'Order</a>' in html:
                    html = html.replace('Order</a>', 'Order</a>' + NAV, 1)
                elif '<nav>' in html:
                    html = html.replace('<nav>', '<nav>' + NAV, 1)
            if 'class="site-header"' not in html:
                header = (
                    '<header class="site-header"><a href="/" class="logo">Root Cause</a>'
                    '<nav class="site-nav">'
                    '<a href="/how-it-works">How it works</a> '
                    '<a href="/scan-food">Food Scanner</a> '
                    '<a href="/buy" class="nav-cta">Order</a> '
                    '<a href="/login">Log in</a></nav></header>'
                )
                html = html.replace('<body>', '<body>' + header, 1)
                if 'class="site-header"' not in html:
                    import re as _re_hdr
                    html = _re_hdr.sub(
                        r'<body([^>]*)>',
                        lambda m: '<body%s>%s' % (m.group(1), header),
                        html,
                        count=1,
                    )
            if 'site-footer' in html:
                import re
                html = re.sub(
                    r'<footer class="site-footer">.*?</footer>',
                    FOOTER.split('<style>')[0],
                    html,
                    count=1,
                    flags=re.DOTALL,
                )
            elif '</body>' in html:
                html = html.replace('</body>', FOOTER + '</body>', 1)
            if response.status_code == 404 and 'noindex' not in html:
                html = html.replace('<head>', '<head><meta name="robots" content="noindex, nofollow">', 1)
            response.set_data(html)
        except Exception as exc:
            print(f'[Root Cause] SEO after_request skipped: {exc}')
        return response

    print('[Root Cause] Registered /privacy /terms /refunds + SEO robots/sitemap')
