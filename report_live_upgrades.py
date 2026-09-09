"""Live upgrades: wellness plan, food scanner history, admin health age."""
import json
import os
import re


def _brand_health_age_and_move_grok(html, ai_html=None):
    if not html:
        return html or ''
    return html.replace('Your Overall Health Score', 'Your Health Age').replace('>Overall Health Score<', '>Your Health Age<')


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
        if not user:
            return False
        if getattr(user, 'is_admin', False):
            return True
        return _normalize_email(user.email) == _normalize_email(report.user_email)

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
        data = _load_overrides()
        data[_normalize_email(email)] = int(age)
        with open(_override_path(), 'w', encoding='utf-8') as fh:
            json.dump(data, fh)

    def _apply_plan(report):
        html = report.generated_report or report.original_generated_report or ''
        name = _client_display_name(report.user_email)
        html = _brand_health_age_and_move_grok(html, report.ai_recommendations)
        html = ensure_client_analysis(html, report.raw_data or '', client_name=name)
        age = _load_overrides().get(_normalize_email(report.user_email))
        if age:
            html = re.sub(r'(<strong>Biometric age:</strong>\s*)\d+', r'\g<1>%s' % age, html, count=1)
            html = re.sub(r'(Your Health Age[\s\S]{0,200}?)(\d{2,3})', r'\g<1>%s' % age, html, count=1)
        if html and html != (report.generated_report or ''):
            report.generated_report = html
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return html

    def view_report(report_id):
        current_user = _get_current_user()
        if not current_user:
            return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _owns(report, current_user):
            abort(403)
        if not current_user.is_admin and not report.approved:
            abort(403)
        _apply_plan(report)
        view = request.args.get('view', 'scan')
        if view not in ('scan', 'original', 'updates'):
            view = 'scan'
        return render_template('report_view.html', report=report, view=view,
                               user={'name': session.get('name', 'Client')},
                               report_id=report.id, grok_terms=collect_grok_terms(report),
                               admin_preview=False)

    def download_report_pdf(report_id):
        current_user = _get_current_user()
        if not current_user:
            return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _owns(report, current_user):
            abort(403)
        html = _apply_plan(report) or report.generated_report or ''
        pdf_name = 'report_%s.pdf' % report.id
        try:
            os.makedirs(reports_dir, exist_ok=True)
            base_dir = reports_dir
        except Exception:
            base_dir = '/tmp'
            os.makedirs(base_dir, exist_ok=True)
        save_report_pdf(html, os.path.join(base_dir, pdf_name))
        report.pdf_filename = pdf_name
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        safe_title = re.sub(r'[^\w\s\-]+', '', (report.title or 'report')).strip() or 'report'
        return send_from_directory(base_dir, pdf_name, as_attachment=True, download_name=re.sub(r'\s+', '-', safe_title)[:80] + '.pdf')

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
        if not current_user:
            return redirect(url_for('login'))
        from food_scanner import client_flags_from_scan
        flags = client_flags_from_scan(_client_scan_raw(current_user))
        return render_template('food_scanner.html', personal_flags=flags)

    def api_food_barcode():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from food_scanner import scan_barcode_for_client
        data = request.get_json(silent=True) or {}
        result = scan_barcode_for_client(data.get('barcode') or '', _client_scan_raw(current_user))
        return jsonify(_store_food(current_user, result))

    def api_food_photo():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from food_scanner import scan_photo_for_client
        data = request.get_json(silent=True) or {}
        result = scan_photo_for_client(data.get('image_b64') or '', data.get('mime') or 'image/jpeg', _client_scan_raw(current_user))
        return jsonify(_store_food(current_user, result))

    def api_food_search():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from food_scanner import search_product_name
        data = request.get_json(silent=True) or {}
        return jsonify({'ok': True, 'results': search_product_name(data.get('q') or '')})

    def api_food_history():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'items': []}), 401
        from food_scan_history import sorted_history
        sort = request.args.get('sort') or 'date_desc'
        return jsonify({'ok': True, 'items': sorted_history(current_user.email, sort)})

    def api_food_guides():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False}), 401
        from food_scanner import client_flags_from_scan
        from food_guides import lists_for_flags
        flags = client_flags_from_scan(_client_scan_raw(current_user))
        top, low = lists_for_flags(flags)
        return jsonify({'ok': True, 'flags': flags, 'top': top, 'low': low})

    def admin_set_health_age():
        current_user = _get_current_user()
        if not current_user or not getattr(current_user, 'is_admin', False):
            abort(403)
        email = _normalize_email(request.form.get('email') or request.form.get('user_email') or '')
        try:
            age = int(request.form.get('health_age') or 0)
        except ValueError:
            age = 0
        if not email or not (12 <= age <= 110):
            flash('Enter a client email and a Health Age between 12 and 110.', 'error')
            return redirect(url_for('admin'))
        _save_override(email, age)
        flash('Health Age for %s set to %s. Open their report to see it.' % (email, age), 'success')
        return redirect(url_for('admin'))

    app.view_functions['view_report'] = view_report
    app.view_functions['download_report_pdf'] = download_report_pdf
    app.add_url_rule('/food-scanner', 'food_scanner', food_scanner_page, methods=['GET'])
    app.add_url_rule('/api/food-scan/barcode', 'api_food_barcode', api_food_barcode, methods=['POST'])
    app.add_url_rule('/api/food-scan/photo', 'api_food_photo', api_food_photo, methods=['POST'])
    app.add_url_rule('/api/food-scan/search', 'api_food_search', api_food_search, methods=['POST'])
    app.add_url_rule('/api/food-scan/history', 'api_food_history', api_food_history, methods=['GET'])
    app.add_url_rule('/api/food-scan/guides', 'api_food_guides', api_food_guides, methods=['GET'])
    app.add_url_rule('/admin/health-age', 'admin_set_health_age', admin_set_health_age, methods=['POST'])

    _orig_dash = app.view_functions.get('dashboard')
    if _orig_dash is not None:
        def dashboard_with_scanner(*args, **kwargs):
            resp = _orig_dash(*args, **kwargs)
            try:
                data = resp.get_data(as_text=True)
                if 'food-scanner' not in data and 'Dashboard' in data:
                    data = data.replace('</h1>', '</h1><p style="margin:1rem 0;"><a class="btn btn-primary" href="/food-scanner">Scan food at the store</a></p>', 1)
                    resp.set_data(data)
            except Exception:
                pass
            return resp
        app.view_functions['dashboard'] = dashboard_with_scanner

    _orig_admin = app.view_functions.get('admin')
    if _orig_admin is not None:
        def admin_with_score(*args, **kwargs):
            resp = _orig_admin(*args, **kwargs)
            try:
                data = resp.get_data(as_text=True)
                if 'admin-health-age' not in data and 'Admin Panel' in data:
                    box = (
                        '<div class="card" id="admin-health-age" style="margin:1rem 0;">'
                        '<h3>Set client Health Age</h3>'
                        '<form method="POST" action="/admin/health-age">'
                        '<p><input name="email" placeholder="client email" required> '
                        '<input name="health_age" type="number" min="12" max="110" placeholder="Health Age" required> '
                        '<button class="btn btn-primary" type="submit">Save Health Age</button></p></form>'
                        '<p class="rec-note">This overrides the biometric / Health Age shown on that client report.</p></div>'
                    )
                    data = data.replace('Admin Panel', 'Admin Panel', 1)
                    data = data.replace('<h1', box + '<h1', 1)
                    resp.set_data(data)
            except Exception:
                pass
            return resp
        app.view_functions['admin'] = admin_with_score

    print('[Root Cause] Applied food history + guides + admin health age')
