"""Live upgrades: Health Age + resilient PDF (fixed ownership check)."""
import os
import re
import traceback


def _brand_health_age_and_move_grok(html, ai_html=None):
    if not html:
        return html or ''
    html = html.replace('Your Overall Health Score', 'Your Health Age')
    html = html.replace('>Overall Health Score<', '>Your Health Age<')
    html = re.sub(r'(Previous\s+)(\d+\s*\u2192)', r'\1Health Age \2', html, count=3)
    ai = (ai_html or '').strip()
    if ai and 'id="grok-analysis"' not in html and 'Your Health Age' in html:
        grok_wrap = (
            '<section class="scan-section grok-top-section" id="grok-analysis">'
            + (ai if re.search(r'<h[23]', ai, re.I) else
               '<h2>Grok Analysis</h2><p class="scan-lead">Personalized interpretation of your scan results.</p>' + ai)
            + '</section>'
        )
        idx = html.find('Your Health Age')
        if idx >= 0:
            html = html[:idx] + grok_wrap + html[idx:]
        else:
            html = grok_wrap + html
    return html


def apply_report_upgrades(app, db, Report, reports_dir):
    from flask import redirect, url_for, flash, abort, request, render_template, session, send_from_directory
    from report_generator import generate_report_html
    from pdf_service import save_report_pdf
    from grok_assistant import collect_grok_terms
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
    _client_display_name = helpers['_client_display_name']
    def _normalize_email(email):
        return (email or '').strip().lower()
    def _owns(report, user):
        if not user:
            return False
        if getattr(user, 'is_admin', False):
            return True
        return _normalize_email(user.email) == _normalize_email(report.user_email)
    helpers['_user_owns_report'] = lambda report: _owns(report, _get_current_user())

    def view_report(report_id):
        current_user = _get_current_user()
        if not current_user:
            return redirect(url_for('login'))
        report = Report.query.get_or_404(report_id)
        if not _owns(report, current_user):
            abort(403)
        if not current_user.is_admin and not report.approved:
            abort(403)
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
        html = report.generated_report or report.original_generated_report or ''
        pdf_name = f'report_{report.id}.pdf'
        os.makedirs(reports_dir, exist_ok=True)
        pdf_path = os.path.join(reports_dir, pdf_name)
        save_report_pdf(html, pdf_path)
        report.pdf_filename = pdf_name
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return send_from_directory(reports_dir, pdf_name, as_attachment=True)

    app.view_functions['view_report'] = view_report
    app.view_functions['download_report_pdf'] = download_report_pdf

    _orig_admin = app.view_functions.get('admin')
    if _orig_admin is not None:
        def admin_safe(*args, **kwargs):
            try:
                resp = _orig_admin(*args, **kwargs)
                try:
                    data = resp.get_data(as_text=True)
                    if 'id="scan_pdfs"' in data:
                        data = data.replace('accept=".pdf"', 'accept=".pdf,.txt,text/plain"')
                        data = data.replace('Upload Scan PDFs', 'Upload Scan PDFs or TXT')
                        resp.set_data(data)
                except Exception:
                    pass
                return resp
            except Exception as exc:
                print(f'[Root Cause] admin fatal: {exc}')
                traceback.print_exc()
                flash(f'Report generation failed: {type(exc).__name__}: {exc}. Upload a .txt or a small PDF.', 'error')
                return redirect(url_for('admin'))
        app.view_functions['admin'] = admin_safe
    print('[Root Cause] Applied live upgrades + TXT accept on admin form')
