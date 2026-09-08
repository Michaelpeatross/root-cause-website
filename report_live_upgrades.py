"""Live upgrades: client wellness plan on every report + PDF."""
import os
import re


def _brand_health_age_and_move_grok(html, ai_html=None):
    if not html:
        return html or ''
    return html.replace('Your Overall Health Score', 'Your Health Age').replace('>Overall Health Score<', '>Your Health Age<')


def apply_report_upgrades(app, db, Report, reports_dir):
    from flask import redirect, url_for, abort, request, render_template, session, send_from_directory
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

    def _apply_plan(report):
        html = report.generated_report or report.original_generated_report or ''
        name = _client_display_name(report.user_email)
        html = _brand_health_age_and_move_grok(html, report.ai_recommendations)
        html = ensure_client_analysis(html, report.raw_data or '', client_name=name)
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
        if not current_user.is_admin and not report.approved:
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
        safe_title = re.sub(r'\s+', '-', safe_title)[:80]
        return send_from_directory(base_dir, pdf_name, as_attachment=True, download_name=safe_title + '.pdf')

    app.view_functions['view_report'] = view_report
    app.view_functions['download_report_pdf'] = download_report_pdf
    print('[Root Cause] Applied client wellness plan on reports and PDFs')
