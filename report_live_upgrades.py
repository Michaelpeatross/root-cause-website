"""Live upgrades: Health Scores on view + on-demand PDF for existing reports."""
import os


def apply_report_upgrades(app, db, Report, reports_dir):
    """Replace view_report and download_report_pdf with upgraded versions."""
    from flask import (
        redirect, url_for, flash, abort, request, render_template, session,
        send_from_directory,
    )
    from report_generator import generate_report_html
    from pdf_service import save_report_pdf
    from grok_assistant import collect_grok_terms

    import sys
    mod = sys.modules.get('app')
    if mod is None:
        mod = sys.modules.get('__main__')
    helpers = {}
    for candidate in (mod, sys.modules.get('app'), sys.modules.get('__main__')):
        if candidate is None:
            continue
        d = vars(candidate)
        if '_get_current_user' in d:
            helpers = d
            break
    if not helpers:
        import inspect
        for fr in inspect.stack():
            if '_get_current_user' in fr.frame.f_globals:
                helpers = fr.frame.f_globals
                break
    if not helpers:
        raise RuntimeError('Could not locate app helpers for live upgrades')

    _get_current_user = helpers['_get_current_user']
    _user_owns_report = helpers['_user_owns_report']
    _report_has_substantive_html = helpers['_report_has_substantive_html']
    _client_display_name = helpers['_client_display_name']
    _prefer_full_scan_template = helpers['_prefer_full_scan_template']

    def _rebuild_html_with_scores(report):
        """Rebuild report HTML so Health Age + scores appear; persist on the report."""
        html = report.generated_report or report.original_generated_report or ''
        needs = ('health-overall-card' not in html) or ('Your Health Age' not in html)
        if not needs:
            return html
        if not (report.raw_data or '').strip():
            return html
        try:
            client_name = _client_display_name(report.user_email)
            prefer_template = True  # force Full Scan layout so Body Overview always runs
            rebuilt = generate_report_html(
                report.user_email,
                report.title or 'Full Scan',
                report.raw_data,
                ai_recommendations_html=report.ai_recommendations,
                client_name=client_name,
                prefer_template=prefer_template,
                blood_reconciliation_html=report.blood_reconciliation_html,
            )
            if rebuilt and len(rebuilt) > 200:
                report.generated_report = rebuilt
                if not report.original_generated_report or 'Your Health Age' not in (report.original_generated_report or ''):
                    report.original_generated_report = rebuilt
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return rebuilt
        except Exception as exc:
            print(f'[Root Cause] Health Score rebuild failed for report {report.id}: {exc}')
            import traceback
            traceback.print_exc()
        return html

    for endpoint in ('view_report', 'download_report_pdf'):
        app.view_functions.pop(endpoint, None)
        try:
            rules_to_remove = [r for r in list(app.url_map.iter_rules()) if r.endpoint == endpoint]
            for r in rules_to_remove:
                app.url_map._rules.remove(r)
            app.url_map._rules_by_endpoint.pop(endpoint, None)
            app.url_map.update()
        except Exception as exc:
            print(f'[Root Cause] Rule cleanup for {endpoint}: {exc}')

    @app.route('/reports/<int:report_id>')
    def view_report(report_id):
        current_user = _get_current_user()
        if not current_user:
            return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _user_owns_report(report) or not (report.generated_report or report.original_generated_report):
            abort(403)
        if not current_user.is_admin and not report.approved:
            abort(403)
        _rebuild_html_with_scores(report)
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

    @app.route('/reports/<int:report_id>/pdf')
    def download_report_pdf(report_id):
        current_user = _get_current_user()
        if not current_user:
            return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _user_owns_report(report):
            abort(403)
        if not current_user.is_admin and not report.approved:
            abort(403)

        html = report.generated_report or report.original_generated_report or ''
        if not html or len(html.strip()) < 40:
            flash(
                'This report has no scan findings yet — PDF download is not available.',
                'error',
            )
            return redirect(url_for('dashboard'))

        html = _rebuild_html_with_scores(report) or html

        pdf_name = report.pdf_filename or f'report_{report.id}.pdf'
        pdf_path = os.path.join(reports_dir, pdf_name)

        # Always regenerate PDF so Health Age is included
        if not save_report_pdf(html, pdf_path):
            flash(
                'Could not generate PDF for this report. Please try again in a moment.',
                'error',
            )
            return redirect(url_for('dashboard'))

        report.pdf_filename = pdf_name
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return send_from_directory(
            reports_dir,
            pdf_name,
            as_attachment=True,
            download_name=f'{(report.title or "report").replace("/", "-")}.pdf',
        )

    def _save_pdf_for_report(report, html_report):
        pdf_name = f'report_{report.id}.pdf'
        pdf_path = os.path.join(reports_dir, pdf_name)
        try:
            if save_report_pdf(html_report, pdf_path):
                report.pdf_filename = pdf_name
                return True
            print(f'[Root Cause] PDF create returned errors for report {report.id}')
        except Exception as exc:
            print(f'[Root Cause] PDF save exception for report {report.id}: {exc}')
        return False

    helpers['_save_pdf_for_report'] = _save_pdf_for_report
    if mod is not None:
        setattr(mod, '_save_pdf_for_report', _save_pdf_for_report)

    print('[Root Cause] Applied Health Score + PDF live upgrades')
