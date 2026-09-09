"""Live upgrades: plain client reports, food scanner, meal diary."""
import json, os, re
FOOD_FAB = ('<a href="/food-scanner" id="food-scan-fab" style="position:fixed;left:16px;bottom:22px;z-index:2147483646;background:#1b4332;color:#fff;padding:11px 15px;border-radius:999px;text-decoration:none;font-weight:700;box-shadow:0 8px 18px rgba(0,0,0,.22);font-size:14px;">Scan Food</a>')

def apply_report_upgrades(app, db, Report, reports_dir):
    from flask import redirect, url_for, abort, request, render_template, session, send_from_directory, jsonify, flash
    from pdf_service import save_report_pdf
    from grok_assistant import collect_grok_terms
    from client_analysis_blocks import ensure_client_analysis
    import sys
    mod = sys.modules.get('app') or sys.modules.get('__main__')
    helpers = vars(mod) if mod and '_get_current_user' in vars(mod) else {}
    if not helpers:
        import inspect
        for fr in inspect.stack():
            if '_get_current_user' in fr.frame.f_globals:
                helpers = fr.frame.f_globals
                break
    if not helpers:
        raise RuntimeError('Could not locate app helpers for live upgrades')
    _get_current_user = helpers['_get_current_user']
    _client_display_name = helpers.get('_client_display_name') or (lambda e: (e or 'Client').split('@')[0])
    def _normalize_email(email):
        return (email or '').strip().lower()
    def _owns(report, user):
        return bool(user) and (getattr(user, 'is_admin', False) or _normalize_email(user.email) == _normalize_email(report.user_email))
    def _client_scan_raw(user):
        if not user:
            return ''
        for report in Report.query.filter_by(user_email=user.email).order_by(Report.id.desc()).all():
            if (report.raw_data or '').strip():
                return report.raw_data
        return ''
    def _override_path():
        base = os.environ.get('DATA_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, 'health_age_overrides.json')
    def _load_overrides():
        try:
            with open(_override_path(), 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    def _save_override(email, age):
        data = _load_overrides(); data[_normalize_email(email)] = int(age)
        with open(_override_path(), 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
    def _apply_plan(report):
        name = _client_display_name(report.user_email)
        try:
            from client_plain_language import client_report_html
            html = client_report_html(report.raw_data or '', name, report.title or '')
        except Exception:
            html = report.generated_report or report.original_generated_report or ''
        html = ensure_client_analysis(html, report.raw_data or '', client_name=name)
        age = _load_overrides().get(_normalize_email(report.user_email))
        if age:
            html = re.sub(r'(<strong>Biometric age:</strong>\\s*)\\d+', r'\\g<1>%s' % age, html, count=1)
        if html and html != (report.generated_report or ''):
            report.generated_report = html
            try: db.session.commit()
            except Exception: db.session.rollback()
        return html
    def view_report(report_id):
        current_user = _get_current_user()
        if not current_user: return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _owns(report, current_user): abort(403)
        if not current_user.is_admin and not report.approved: abort(403)
        _apply_plan(report)
        view = request.args.get('view', 'scan')
        if view not in ('scan', 'original', 'updates'): view = 'scan'
        return render_template('report_view.html', report=report, view=view, user={'name': session.get('name', 'Client')}, report_id=report.id, grok_terms=collect_grok_terms(report), admin_preview=False)
    def download_report_pdf(report_id):
        current_user = _get_current_user()
        if not current_user: return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _owns(report, current_user): abort(403)
        html = _apply_plan(report) or report.generated_report or ''
        pdf_name = 'report_%s.pdf' % report.id
        try:
            os.makedirs(reports_dir, exist_ok=True); base_dir = reports_dir
        except Exception:
            base_dir = '/tmp'; os.makedirs(base_dir, exist_ok=True)
        save_report_pdf(html, os.path.join(base_dir, pdf_name))
        report.pdf_filename = pdf_name
        try: db.session.commit()
        except Exception: db.session.rollback()
        safe_title = re.sub(r'[^\\w\\s\\-]+', '', (report.title or 'report')).strip() or 'report'
        return send_from_directory(base_dir, pdf_name, as_attachment=True, download_name=re.sub(r'\\s+', '-', safe_title)[:80] + '.pdf')
    def _store_food(user, result):
        if result and result.get('ok'):
            try:
                from food_scan_history import save_scan
                save_scan(user.email, result)
            except Exception as exc:
                print('[Root Cause] food history save failed', exc)
        return result
    def food_scanner_page():
        current_user = _get_current_user()
        if not current_user: return redirect(url_for('login'))
        from food_scanner import client_flags_from_scan
        return render_template('food_scanner.html', personal_flags=client_flags_from_scan(_client_scan_raw(current_user)))
    def api_food_barcode():
        current_user = _get_current_user()
        if not current_user: return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from food_scanner import scan_barcode_for_client
        data = request.get_json(silent=True) or {}
        return jsonify(_store_food(current_user, scan_barcode_for_client(data.get('barcode') or '', _client_scan_raw(current_user))))
    def api_food_photo():
        current_user = _get_current_user()
        if not current_user: return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from food_scanner import scan_photo_for_client
        data = request.get_json(silent=True) or {}
        return jsonify(_store_food(current_user, scan_photo_for_client(data.get('image_b64') or '', data.get('mime') or 'image/jpeg', _client_scan_raw(current_user))))
    def api_food_search():
        current_user = _get_current_user()
        if not current_user: return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from food_scanner import search_product_name
        data = request.get_json(silent=True) or {}
        return jsonify({'ok': True, 'results': search_product_name(data.get('q') or '')})
    def api_food_history():
        current_user = _get_current_user()
        if not current_user: return jsonify({'ok': False, 'items': []}), 401
        from food_scan_history import sorted_history
        return jsonify({'ok': True, 'items': sorted_history(current_user.email, request.args.get('sort') or 'date_desc')})
    def api_food_guides():
        current_user = _get_current_user()
        if not current_user: return jsonify({'ok': False}), 401
        from food_scanner import client_flags_from_scan
        from food_guides import lists_for_flags
        from food_scan_history import load_history
        raw = _client_scan_raw(current_user)
        flags = client_flags_from_scan(raw)
        scanned = [row.get('name') or '' for row in load_history(current_user.email)]
        top, low = lists_for_flags(flags, scanned_names=scanned, raw_text=raw)
        return jsonify({'ok': True, 'flags': flags, 'top': top, 'low': low})
    def api_food_meal():
        current_user = _get_current_user()
        if not current_user: return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from meal_photo import analyze_plate_for_client
        from food_diary import save_meal
        data = request.get_json(silent=True) or {}
        result = analyze_plate_for_client(data.get('image_b64') or '', data.get('mime') or 'image/jpeg', _client_scan_raw(current_user))
        if result.get('ok'):
            macros = result.get('macros') or {}; rating = result.get('rating') or {}; product = result.get('product') or {}
            save_meal(current_user.email, {'name': product.get('name'), 'portion': macros.get('portion'), 'calories': macros.get('calories'), 'protein': macros.get('protein'), 'carbs': macros.get('carbs'), 'fat': macros.get('fat'), 'sugar': macros.get('sugar'), 'fiber': macros.get('fiber'), 'score': rating.get('score'), 'label': rating.get('label'), 'notes': macros.get('notes')})
            _store_food(current_user, result)
        return jsonify(result)
    def api_food_diary():
        current_user = _get_current_user()
        if not current_user: return jsonify({'ok': False}), 401
        from food_diary import daily_summary
        return jsonify({'ok': True, **daily_summary(current_user.email)})
    def admin_set_health_age():
        current_user = _get_current_user()
        if not current_user or not getattr(current_user, 'is_admin', False): abort(403)
        email = _normalize_email(request.form.get('email') or '')
        try: age = int(request.form.get('health_age') or 0)
        except ValueError: age = 0
        if not email or not (12 <= age <= 110):
            flash('Enter a client email and a Health Age between 12 and 110.', 'error'); return redirect(url_for('admin'))
        _save_override(email, age)
        flash('Health Age for %s set to %s.' % (email, age), 'success'); return redirect(url_for('admin'))
    app.view_functions['view_report'] = view_report
    app.view_functions['download_report_pdf'] = download_report_pdf
    app.add_url_rule('/food-scanner', 'food_scanner', food_scanner_page, methods=['GET'])
    app.add_url_rule('/api/food-scan/barcode', 'api_food_barcode', api_food_barcode, methods=['POST'])
    app.add_url_rule('/api/food-scan/photo', 'api_food_photo', api_food_photo, methods=['POST'])
    app.add_url_rule('/api/food-scan/search', 'api_food_search', api_food_search, methods=['POST'])
    app.add_url_rule('/api/food-scan/history', 'api_food_history', api_food_history, methods=['GET'])
    app.add_url_rule('/api/food-scan/guides', 'api_food_guides', api_food_guides, methods=['GET'])
    app.add_url_rule('/api/food-scan/meal', 'api_food_meal', api_food_meal, methods=['POST'])
    app.add_url_rule('/api/food-scan/diary', 'api_food_diary', api_food_diary, methods=['GET'])
    app.add_url_rule('/admin/health-age', 'admin_set_health_age', admin_set_health_age, methods=['POST'])
    @app.after_request
    def _food_nav(resp):
        try:
            if 'html' not in (resp.headers.get('Content-Type') or ''): return resp
            data = resp.get_data(as_text=True)
            if not data or 'site-header' not in data: return resp
            if 'Logout' in data or 'Dashboard</a>' in data:
                if '>Scan Food</a>' not in data and 'Dashboard</a>' in data:
                    data = data.replace('>Dashboard</a>', '>Dashboard</a><a href="/food-scanner">Scan Food</a>', 1)
                if 'id="food-scan-fab"' not in data and not (request.path or '').startswith('/food-scanner'):
                    data = data.replace('</body>', FOOD_FAB + '</body>', 1)
                resp.set_data(data)
        except Exception:
            pass
        return resp
    print('[Root Cause] Applied meal diary + Scan Food nav')
