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
    mod = sys.modules.get('app') or sys.modules.get('__main__')
    if mod is None:
        import app as mod

    _get_current_user = mod._get_current_user
    _user_owns_report = mod._user_owns_report
    _report_has_substantive_html = mod._report_has_substantive_html
    _client_display_name = mod._client_display_name
    _prefer_full_scan_template = mod._prefer_full_scan_template

    def _rebuild_html_with_scores(report):
        html = report.generated_report or ''
        if 'health-overall-card' in html:
            return html
        if not (report.raw_data or '').strip():
            return html
        try:
            client_name = _client_display_name(report.user_email)
            prefer_template = _prefer_full_scan_template(report.title, report.raw_data)
            rebuilt = generate_report_html(
                report.user_email,
                report.title,
                report.raw_data,
                ai_recommendations_html=report.ai_recommendations,
                client_name=client_name,
                prefer_template=prefer_template,
                blood_reconciliation_html=report.blood_reconciliation_html,
            )
            if rebuilt and 'health-overall-card' in rebuilt:
                report.generated_report = rebuilt
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return rebuilt
        except Exception as exc:
            print(f'[Root Cause] Health Score rebuild failed for report {report.id}: {exc}')
        return html

    for endpoint in ('view_report', 'download_report_pdf'):
        app.view_functions.pop(endpoint, None)
        app.url_map._rules = [r for r in app.url_map._rules if r.endpoint != endpoint]
        app.url_map._rules_by_endpoint.pop(endpoint, None)

    @app.route('/reports/<int:report_id>')
    def view_report(report_id):
        current_user = _get_current_user()
        if not current_user:
            return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _user_owns_report(report) or not report.generated_report:
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
        if not _report_has_substantive_html(report):
            flash(
                'This report has no scan findings yet — PDF download is not available.',
                'error',
            )
            return redirect(url_for('dashboard'))

        html = _rebuild_html_with_scores(report)
        pdf_name = report.pdf_filename or f'report_{report.id}.pdf'
        pdf_path = os.path.join(reports_dir, pdf_name)
        if not os.path.isfile(pdf_path):
            if not save_report_pdf(html or report.generated_report, pdf_path):
                flash(
                    'Could not generate PDF for this report. Please try again.',
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
            report.pdf_filename,
            as_attachment=True,
            download_name=f'{report.title or "report"}.pdf',
        )

    print('[Root Cause] Applied Health Score + PDF live upgrades')
