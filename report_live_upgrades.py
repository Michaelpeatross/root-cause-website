"""Live upgrades: wellness report chrome, plain client blocks, food scanner, meal diary."""
import json
import os
import re

FOOD_FAB = (
    '<a href="/food-scanner" id="food-scan-fab" style="position:fixed;left:16px;bottom:22px;'
    'z-index:2147483646;background:#1b4332;color:#fff;padding:11px 15px;border-radius:999px;'
    'text-decoration:none;font-weight:700;box-shadow:0 8px 18px rgba(0,0,0,.22);font-size:14px;">'
    'Scan Food</a>'
)


def apply_report_upgrades(app, db, Report, reports_dir):
    from flask import (
        redirect, url_for, abort, request, render_template, session,
        send_from_directory, jsonify, flash,
    )
    from pdf_service import save_report_pdf
    from grok_assistant import collect_grok_terms
    from client_analysis_blocks import ensure_client_analysis
    import sys
    import traceback

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
    _client_display_name = helpers.get('_client_display_name') or (
        lambda e: (e or 'Client').split('@')[0]
    )

    def _normalize_email(email):
        return (email or '').strip().lower()

    def _owns(report, user):
        return bool(user) and (
            getattr(user, 'is_admin', False)
            or _normalize_email(user.email) == _normalize_email(report.user_email)
        )

    def _client_scan_raw(user):
        if not user:
            return ''
        for report in Report.query.filter_by(user_email=user.email).order_by(Report.id.desc()).all():
            if (report.raw_data or '').strip():
                return report.raw_data
        return ''

    def _override_path():
        base = os.environ.get('DATA_DIR') or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data'
        )
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

    def _scan_label(row):
        title = getattr(row, 'title', None) or ''
        match = re.search(
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}',
            title,
            re.I,
        )
        if match:
            return match.group(0)
        stamp = getattr(row, 'date', None)
        if stamp:
            return str(stamp)[:10]
        return 'Earlier scan'

    def _earlier_scans(report):
        """Older scans for this client, oldest first, so the report can show change."""
        try:
            from organ_ratings import organ_signals
        except Exception:
            return []
        email = _normalize_email(getattr(report, 'user_email', ''))
        if not email:
            return []
        found = []
        try:
            rows = Report.query.order_by(Report.id.asc()).all()
        except Exception:
            return []
        for row in rows:
            if getattr(row, 'id', None) == getattr(report, 'id', None):
                continue
            if _normalize_email(getattr(row, 'user_email', '')) != email:
                continue
            if int(getattr(row, 'id', 0) or 0) > int(getattr(report, 'id', 0) or 0):
                continue
            raw = getattr(row, 'raw_data', None) or ''
            if len(raw.strip()) < 40:
                continue
            signals = organ_signals(raw)
            if not signals:
                continue
            found.append({'label': _scan_label(row), 'signals': signals})
        return found

    def _health_records_block(report):
        ClientDocument = helpers.get('ClientDocument')
        if ClientDocument is None:
            return ''
        documents_dir = helpers.get('documents_dir') or ''
        email = _normalize_email(getattr(report, 'user_email', ''))
        try:
            docs = ClientDocument.query.filter(
                db.func.lower(ClientDocument.user_email) == email
            ).order_by(ClientDocument.id.asc()).all()
        except Exception as exc:
            print('[Root Cause] health record lookup failed: %s' % exc)
            return ''
        changed = False
        try:
            from health_records_report import refresh_document_text, health_records_html
        except Exception as exc:
            print('[Root Cause] health record module failed: %s' % exc)
            return ''
        for doc in docs:
            try:
                if refresh_document_text(doc, documents_dir):
                    changed = True
            except Exception:
                continue
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        try:
            return health_records_html(docs, client_name=_client_display_name(email))
        except Exception as exc:
            print('[Root Cause] health record html failed: %s' % exc)
            return ''

    def _apply_plan(report):
        name = _client_display_name(report.user_email)
        html = report.generated_report or report.original_generated_report or ''
        raw = report.raw_data or ''
        needs_rebuild = bool(raw.strip()) and (
            'health-overall-card' not in html
            and 'id="wellness-report-chrome"' not in html
            and 'class="scan-report"' not in html
            and 'class="bio-report"' not in html
        )
        if needs_rebuild:
            try:
                from report_generator import generate_report_html
                rebuilt = generate_report_html(
                    report.user_email,
                    report.title or 'Full Scan',
                    raw,
                    ai_recommendations_html=getattr(report, 'ai_recommendations', None),
                    client_name=name,
                    prefer_template=True,
                    blood_reconciliation_html=getattr(report, 'blood_reconciliation_html', None),
                )
                if rebuilt and len(rebuilt) > 200:
                    html = rebuilt
            except Exception as exc:
                print('[Root Cause] wellness rebuild failed for report %s: %s' % (getattr(report, 'id', '?'), exc))
                traceback.print_exc()
        try:
            from wellness_template import wrap_wellness_report, clean_client_report
            html = wrap_wellness_report(html, client_name=name, title=report.title, raw_data=raw)
        except Exception as exc:
            print('[Root Cause] wellness wrap failed: %s' % exc)
            clean_client_report = None
        try:
            from system_plain import inject_system_plain_cards
            html = inject_system_plain_cards(html)
        except Exception as exc:
            print('[Root Cause] system plain cards failed: %s' % exc)
        calendar_age = biometric_age = None
        cal_match = re.search(r'Calendar age:</strong>\s*(\d+)', html or '') or re.search(
            r'class="age-cal"[\s\S]{0,180}?class="age-num">\s*(\d+)', html or ''
        )
        bio_match = re.search(r'Biometric age:</strong>\s*(\d+)', html or '') or re.search(
            r'class="age-bio"[\s\S]{0,180}?class="age-num">\s*(\d+)', html or ''
        )
        if cal_match:
            calendar_age = int(cal_match.group(1))
        if bio_match:
            biometric_age = int(bio_match.group(1))
        override = _load_overrides().get(_normalize_email(report.user_email))
        if override:
            biometric_age = int(override)
        try:
            html = ensure_client_analysis(html, raw, client_name=name)
        except Exception as exc:
            print('[Root Cause] client analysis blocks failed: %s' % exc)
        try:
            from wellness_template import place_findings_first
            html = place_findings_first(
                html, raw, client_name=name,
                calendar_age=calendar_age, biometric_age=biometric_age,
                previous_scans=_earlier_scans(report),
                health_html=_health_records_block(report),
            )
        except Exception as exc:
            print('[Root Cause] findings-first layout failed: %s' % exc)
        try:
            if clean_client_report:
                html = clean_client_report(html)
        except Exception as exc:
            print('[Root Cause] client report clean failed: %s' % exc)
        if html and html != (report.generated_report or ''):
            report.generated_report = html
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        _persist_report_pdf(report, html)
        return html

    def _persist_report_pdf(report, html):
        """Keep a PDF copy on the persistent disk for this report. Never delete older reports."""
        if not html or len(html.strip()) < 40 or not getattr(report, 'id', None):
            return False
        pdf_name = 'report_%s.pdf' % report.id
        try:
            os.makedirs(reports_dir, exist_ok=True)
            path = os.path.join(reports_dir, pdf_name)
            ok = bool(save_report_pdf(html, path))
        except Exception as exc:
            print('[Root Cause] keep pdf failed for report %s: %s' % (getattr(report, 'id', '?'), exc))
            return False
        if not ok or not os.path.isfile(os.path.join(reports_dir, pdf_name)):
            return False
        if report.pdf_filename != pdf_name:
            report.pdf_filename = pdf_name
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return True

    def _restore_published_reports():
        """Put sent reports back on the client page if a later edit hid them."""
        try:
            from document_service import report_html_has_findings, scan_text_has_content
        except Exception:
            report_html_has_findings = lambda html: False
            scan_text_has_content = lambda text: len((text or '').strip()) > 80
        changed = False
        try:
            rows = Report.query.all()
        except Exception as exc:
            print('[Root Cause] restore reports failed: %s' % exc)
            return
        for report in rows:
            html = report.generated_report or ''
            original = getattr(report, 'original_generated_report', None) or ''
            raw = report.raw_data or ''
            real = (
                report_html_has_findings(html)
                or report_html_has_findings(original)
                or scan_text_has_content(raw)
            )
            was_sent = bool(
                report.email_sent or report.sms_sent or (original and len(original) > 200) or len((raw or '').strip()) > 80
            )
            if real and was_sent and not report.approved:
                report.approved = True
                if not report.approved_at:
                    report.approved_at = report.date or ''
                changed = True
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    _restore_published_reports()

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
        return render_template(
            'report_view.html',
            report=report,
            view=view,
            user={'name': session.get('name', 'Client')},
            report_id=report.id,
            grok_terms=collect_grok_terms(report),
            admin_preview=False,
        )

    def download_report_pdf(report_id):
        current_user = _get_current_user()
        if not current_user:
            return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _owns(report, current_user):
            abort(403)
        if not current_user.is_admin and not getattr(report, 'approved', True):
            abort(403)
        html = _apply_plan(report) or report.generated_report or ''
        if not html or len(html.strip()) < 40:
            flash('This report has no scan findings yet — PDF download is not available.', 'error')
            return redirect(url_for('admin') if getattr(current_user, 'is_admin', False) else url_for('dashboard'))
        pdf_name = 'report_%s.pdf' % report.id
        try:
            os.makedirs(reports_dir, exist_ok=True)
            base_dir = reports_dir
        except Exception:
            base_dir = '/tmp'
            os.makedirs(base_dir, exist_ok=True)
        ok = False
        try:
            ok = bool(save_report_pdf(html, os.path.join(base_dir, pdf_name)))
        except Exception as exc:
            print('[Root Cause] save_report_pdf exception: %s' % exc)
            traceback.print_exc()
        if not ok or not os.path.isfile(os.path.join(base_dir, pdf_name)):
            flash('Could not generate the PDF for this report. Try again in a moment.', 'error')
            return redirect(url_for('admin') if getattr(current_user, 'is_admin', False) else url_for('dashboard'))
        report.pdf_filename = pdf_name
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        safe_title = re.sub(r'[^\w\s\-]+', '', (report.title or 'report')).strip() or 'report'
        return send_from_directory(
            base_dir,
            pdf_name,
            as_attachment=True,
            download_name=re.sub(r'\s+', '-', safe_title)[:80] + '.pdf',
        )

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
        return render_template('food_scanner.html', personal_flags=client_flags_from_scan(_client_scan_raw(current_user)))

    def api_food_barcode():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from food_scanner import scan_barcode_for_client
        data = request.get_json(silent=True) or {}
        return jsonify(_store_food(current_user, scan_barcode_for_client(data.get('barcode') or '', _client_scan_raw(current_user))))

    def api_food_photo():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from food_scanner import scan_photo_for_client
        data = request.get_json(silent=True) or {}
        return jsonify(_store_food(current_user, scan_photo_for_client(data.get('image_b64') or '', data.get('mime') or 'image/jpeg', _client_scan_raw(current_user))))

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
        return jsonify({'ok': True, 'items': sorted_history(current_user.email, request.args.get('sort') or 'date_desc')})

    def api_food_guides():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False}), 401
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
        if not current_user:
            return jsonify({'ok': False, 'error': 'Please log in.'}), 401
        from meal_photo import analyze_plate_for_client
        from food_diary import save_meal
        data = request.get_json(silent=True) or {}
        result = analyze_plate_for_client(data.get('image_b64') or '', data.get('mime') or 'image/jpeg', _client_scan_raw(current_user))
        if result.get('ok'):
            macros = result.get('macros') or {}
            rating = result.get('rating') or {}
            product = result.get('product') or {}
            save_meal(current_user.email, {
                'name': product.get('name'), 'portion': macros.get('portion'),
                'calories': macros.get('calories'), 'protein': macros.get('protein'),
                'carbs': macros.get('carbs'), 'fat': macros.get('fat'),
                'sugar': macros.get('sugar'), 'fiber': macros.get('fiber'),
                'score': rating.get('score'), 'label': rating.get('label'),
                'notes': macros.get('notes'),
            })
            _store_food(current_user, result)
        return jsonify(result)

    def api_food_diary():
        current_user = _get_current_user()
        if not current_user:
            return jsonify({'ok': False}), 401
        from food_diary import daily_summary
        return jsonify({'ok': True, **daily_summary(current_user.email)})

    def admin_set_health_age():
        current_user = _get_current_user()
        if not current_user or not getattr(current_user, 'is_admin', False):
            abort(403)
        email = _normalize_email(request.form.get('email') or '')
        try:
            age = int(request.form.get('health_age') or 0)
        except ValueError:
            age = 0
        if not email or not (12 <= age <= 110):
            flash('Enter a client email and a Health Age between 12 and 110.', 'error')
            return redirect(url_for('admin'))
        _save_override(email, age)
        flash('Health Age for %s set to %s.' % (email, age), 'success')
        return redirect(url_for('admin'))

    def _pdf_token(report_id):
        import hmac
        import hashlib
        secret = app.secret_key or os.environ.get('SECRET_KEY') or 'root-cause-report-pdf'
        if isinstance(secret, bytes):
            secret = secret.decode('utf-8', errors='replace')
        digest = hmac.new(
            str(secret).encode('utf-8'),
            ('report-pdf:%s' % int(report_id)).encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        return digest[:40]

    def report_mms_pdf(report_id, token):
        import hmac
        from flask import Response
        if not hmac.compare_digest(str(token or ''), _pdf_token(report_id)):
            abort(404)
        report = Report.query.get_or_404(report_id)
        html = _apply_plan(report) or report.generated_report or ''
        from pdf_service import pdf_to_bytes
        data = pdf_to_bytes(html)
        if not data:
            abort(404)
        filename = 'Full-Scan.pdf'
        return Response(
            data,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'inline; filename="%s"' % filename},
        )

    def _approve_and_send_report(report, send_email=False, send_sms=False):
        User = helpers['User']
        user = User.query.filter(
            db.func.lower(User.email) == _normalize_email(report.user_email)
        ).first()
        client_name = _client_display_name(report.user_email)
        client_phone = user.phone if user else ''
        helpers['_publish_report_to_portal'](report)
        html = _apply_plan(report) or report.generated_report or ''
        pdf_bytes = None
        if html and (send_email or send_sms):
            from pdf_service import pdf_to_bytes
            pdf_bytes = pdf_to_bytes(html)
            if pdf_bytes:
                try:
                    os.makedirs(reports_dir, exist_ok=True)
                    pdf_name = 'report_%s.pdf' % report.id
                    with open(os.path.join(reports_dir, pdf_name), 'wb') as handle:
                        handle.write(pdf_bytes)
                    report.pdf_filename = pdf_name
                except Exception as exc:
                    print('[Root Cause] could not store pdf for send: %s' % exc)
        site = os.environ.get('SITE_URL', 'https://www.root-cause-test.com').rstrip('/')
        media_url = None
        if send_sms and pdf_bytes:
            media_url = '%s/reports/%s/mms/%s' % (site, report.id, _pdf_token(report.id))
        from notification_service import deliver_report_to_client
        results = deliver_report_to_client(
            report.user_email,
            client_name,
            client_phone,
            report.title,
            report.plain_text or '',
            pdf_bytes=pdf_bytes,
            send_email=send_email,
            send_sms=send_sms,
            reply_webhook_url=site + '/api/textbelt/reply',
            from_number='+15106801079',
            media_url=media_url,
        )
        messages = []
        for channel, ok, msg in results:
            if channel == 'email' and send_email:
                report.email_sent = bool(ok)
                messages.append(msg)
            elif channel == 'sms' and send_sms:
                report.sms_sent = bool(ok)
                messages.append(msg)
        if not send_email and not send_sms:
            messages.append('Report is on the client portal (no email or text sent).')
        return messages

    helpers['_approve_and_send_report'] = _approve_and_send_report

    _orig_render_dashboard = helpers.get('_render_client_dashboard')

    def _render_client_dashboard(email, admin_preview=False):
        try:
            rows = Report.query.filter(
                db.func.lower(Report.user_email) == _normalize_email(email),
                Report.approved == True,
            ).order_by(Report.id.desc()).all()
            for row in rows:
                if not (row.raw_data or row.generated_report):
                    continue
                pdf_path = os.path.join(reports_dir, 'report_%s.pdf' % row.id)
                if row.id == rows[0].id or not os.path.isfile(pdf_path):
                    _apply_plan(row)
        except Exception as exc:
            print('[Root Cause] portal report sync failed: %s' % exc)
        if _orig_render_dashboard:
            return _orig_render_dashboard(email, admin_preview=admin_preview)
        return redirect(url_for('dashboard'))

    helpers['_render_client_dashboard'] = _render_client_dashboard

    _orig_build_dashboard = helpers.get('_build_dashboard_context')

    def _report_visible(report):
        raw = (getattr(report, 'raw_data', None) or '').strip()
        html = getattr(report, 'generated_report', None) or ''
        original = getattr(report, 'original_generated_report', None) or ''
        try:
            from document_service import report_html_has_findings, scan_text_has_content
            if report_html_has_findings(html) or report_html_has_findings(original):
                return True
            if scan_text_has_content(raw):
                return True
        except Exception:
            pass
        return len(raw) > 80 or len(html) > 400 or len(original) > 400

    def _build_dashboard_context(email):
        ctx = _orig_build_dashboard(email) if _orig_build_dashboard else {}
        try:
            rows = Report.query.filter(
                db.func.lower(Report.user_email) == _normalize_email(email)
            ).order_by(Report.id.desc()).all()
        except Exception as exc:
            print('[Root Cause] past report list failed: %s' % exc)
            return ctx
        changed = False
        visible = []
        for row in rows:
            if not _report_visible(row):
                continue
            if not row.approved:
                row.approved = True
                if not row.approved_at:
                    row.approved_at = row.date or ''
                changed = True
            visible.append(row)
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        if visible:
            ctx['reports'] = visible
            group = helpers.get('_group_reports_by_date')
            ctx['reports_by_date'] = group(visible) if group else {'Reports': visible}
            ctx['report_id'] = visible[0].id
        return ctx

    helpers['_build_dashboard_context'] = _build_dashboard_context

    app.view_functions['view_report'] = view_report
    app.view_functions['download_report_pdf'] = download_report_pdf
    existing = {rule.endpoint for rule in app.url_map.iter_rules()}
    extra = [
        ('/food-scanner', 'food_scanner', food_scanner_page, ['GET']),
        ('/api/food-scan/barcode', 'api_food_barcode', api_food_barcode, ['POST']),
        ('/api/food-scan/photo', 'api_food_photo', api_food_photo, ['POST']),
        ('/api/food-scan/search', 'api_food_search', api_food_search, ['POST']),
        ('/api/food-scan/history', 'api_food_history', api_food_history, ['GET']),
        ('/api/food-scan/guides', 'api_food_guides', api_food_guides, ['GET']),
        ('/api/food-scan/meal', 'api_food_meal', api_food_meal, ['POST']),
        ('/api/food-scan/diary', 'api_food_diary', api_food_diary, ['GET']),
        ('/admin/health-age', 'admin_set_health_age', admin_set_health_age, ['POST']),
        ('/reports/<int:report_id>/mms/<token>', 'report_mms_pdf', report_mms_pdf, ['GET']),
    ]
    for path, endpoint, view, methods in extra:
        app.view_functions[endpoint] = view
        if endpoint not in existing:
            app.add_url_rule(path, endpoint, view, methods=methods)

    @app.after_request
    def _food_nav(resp):
        try:
            if 'html' not in (resp.headers.get('Content-Type') or ''):
                return resp
            data = resp.get_data(as_text=True)
            if not data or 'site-header' not in data:
                return resp
            if 'Logout' in data or 'Dashboard</a>' in data:
                if '>Scan Food</a>' not in data and 'Dashboard</a>' in data:
                    data = data.replace('>Dashboard</a>', '>Dashboard</a><a href="/food-scanner">Scan Food</a>', 1)
                if 'id="food-scan-fab"' not in data and not (request.path or '').startswith(('/food-scanner', '/scan-food', '/nutrition')):
                    data = data.replace('</body>', FOOD_FAB + '</body>', 1)
                resp.set_data(data)
        except Exception:
            pass
        return resp

    print('[Root Cause] Applied wellness report wrap + meal diary + Scan Food nav')
