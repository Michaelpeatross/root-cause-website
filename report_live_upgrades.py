"""Live upgrades: Health Age + resilient PDF (fixed ownership check)."""
import os
import re
import traceback


def _brand_health_age_and_move_grok(html, ai_html=None):
    """Rename overall score to Health Age and move Grok analysis under it."""
    if not html:
        return html or ''

    html = html.replace('Your Overall Health Score', 'Your Health Age')
    html = html.replace('>Overall Health Score<', '>Your Health Age<')
    html = re.sub(
        r'(Previous\s+)(\d+\s*→)',
        r'\1Health Age \2',
        html,
        count=3,
    )

    ai = (ai_html or '').strip()
    if not ai:
        m = re.search(
            r'(<section[^>]*>\s*<h[23][^>]*>\s*(?:🧠\s*)?(?:Personalized Health Options|Grok Analysis)[\s\S]*?</section>)',
            html,
            re.I,
        )
        if m:
            ai = m.group(1)
            html = html.replace(m.group(1), '', 1)

    if ai and 'id="grok-analysis"' not in html and 'Your Health Age' in html:
        grok_wrap = (
            '<section class="scan-section grok-top-section" id="grok-analysis">'
            + (ai if re.search(r'<h[23]', ai, re.I) else
               '<h2>Grok Analysis</h2><p class="scan-lead">Personalized interpretation of your scan results.</p>' + ai)
            + '</section>'
        )
        card_end = re.search(
            r'(class="health-overall-card[\s\S]*?health-score-scale[\s\S]*?</div>\s*</div>)',
            html,
        )
        if card_end:
            pos = card_end.end()
            html = html[:pos] + grok_wrap + html[pos:]
        else:
            idx = html.find('Your Health Age')
            if idx >= 0:
                bar = html.find('health-score-scale', idx)
                if bar > 0:
                    close = html.find('</div>', html.find('</div>', bar) + 1)
                    if close > 0:
                        html = html[:close + 6] + grok_wrap + html[close + 6:]
                    else:
                        html = html[:idx] + grok_wrap + html[idx:]
                else:
                    html = grok_wrap + html
            else:
                html = grok_wrap + html

    if 'health-age-hero' not in html and 'health-overall-card' in html:
        html = html.replace(
            'class="health-overall-card"',
            'class="health-age-hero health-overall-card"',
            1,
        )
    return html


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
    _client_display_name = helpers['_client_display_name']
    _normalize_email = helpers.get('_normalize_email')
    if _normalize_email is None:
        def _normalize_email(email):
            return (email or '').strip().lower()

    def _owns(report, user):
        if not user:
            return False
        if getattr(user, 'is_admin', False):
            return True
        return _normalize_email(user.email) == _normalize_email(report.user_email)

    def _user_owns_report_fixed(report):
        user = _get_current_user()
        return _owns(report, user)

    helpers['_user_owns_report'] = _user_owns_report_fixed
    if mod is not None:
        setattr(mod, '_user_owns_report', _user_owns_report_fixed)

    def _rebuild_html_with_scores(report):
        html = report.generated_report or report.original_generated_report or ''
        try:
            needs = (
                'health-overall-card' not in html
                or 'Your Health Age' not in html
            )
            if (report.raw_data or '').strip() and needs:
                client_name = _client_display_name(report.user_email)
                rebuilt = generate_report_html(
                    report.user_email,
                    report.title or 'Full Scan',
                    report.raw_data,
                    ai_recommendations_html=report.ai_recommendations,
                    client_name=client_name,
                    prefer_template=True,
                    blood_reconciliation_html=report.blood_reconciliation_html,
                )
                if rebuilt and len(rebuilt) > 200:
                    html = rebuilt
            html = _brand_health_age_and_move_grok(html, report.ai_recommendations)
            if html and len(html) > 200 and html != (report.generated_report or ''):
                report.generated_report = html
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception as exc:
            print(f'[Root Cause] Health Age rebuild failed for report {getattr(report, "id", "?")}: {exc}')
            traceback.print_exc()
            try:
                html = _brand_health_age_and_move_grok(html, getattr(report, 'ai_recommendations', None))
            except Exception:
                pass
        return html

    def view_report(report_id):
        try:
            current_user = _get_current_user()
            if not current_user:
                return redirect(url_for('login'))
            report = Report.query.get_or_404(report_id)
            if not _owns(report, current_user):
                abort(403)
            if not (report.generated_report or report.original_generated_report):
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
        except Exception as exc:
            print(f'[Root Cause] view_report error: {exc}')
            traceback.print_exc()
            flash('Could not open this report. Please try again.', 'error')
            return redirect(url_for('dashboard'))

    def download_report_pdf(report_id):
        try:
            current_user = _get_current_user()
            if not current_user:
                return redirect(url_for('login'))
            report = Report.query.get_or_404(report_id)
            if not _owns(report, current_user):
                abort(403)
            if not current_user.is_admin and not report.approved:
                abort(403)

            html = report.generated_report or report.original_generated_report or ''
            if not html or len(html.strip()) < 40:
                flash(
                    'This report has no scan findings yet — PDF download is not available.',
                    'error',
                )
                return redirect(url_for('admin') if current_user.is_admin else url_for('dashboard'))

            try:
                html = _rebuild_html_with_scores(report) or html
            except Exception:
                pass

            pdf_name = f'report_{report.id}.pdf'
            base_dir = reports_dir
            try:
                os.makedirs(base_dir, exist_ok=True)
            except Exception:
                base_dir = '/tmp'
                os.makedirs(base_dir, exist_ok=True)
            pdf_path = os.path.join(base_dir, pdf_name)

            ok = False
            try:
                ok = bool(save_report_pdf(html, pdf_path))
            except Exception as exc:
                print(f'[Root Cause] save_report_pdf exception: {exc}')
                traceback.print_exc()

            if not ok or not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) < 100:
                flash(
                    'Could not generate the PDF for this report. Try again in a moment.',
                    'error',
                )
                return redirect(url_for('admin') if current_user.is_admin else url_for('dashboard'))

            report.pdf_filename = pdf_name
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

            safe_title = re.sub(r'[^\w\s\-]+', '', (report.title or 'report')).strip() or 'report'
            safe_title = re.sub(r'\s+', '-', safe_title)[:80]
            return send_from_directory(
                base_dir,
                pdf_name,
                as_attachment=True,
                download_name=f'{safe_title}.pdf',
            )
        except Exception as exc:
            print(f'[Root Cause] download_report_pdf fatal: {exc}')
            traceback.print_exc()
            flash('PDF download failed. Please try again.', 'error')
            try:
                u = _get_current_user()
                if u and u.is_admin:
                    return redirect(url_for('admin'))
            except Exception:
                pass
            return redirect(url_for('dashboard'))

    def _save_pdf_for_report(report, html_report):
        pdf_name = f'report_{report.id}.pdf'
        pdf_path = os.path.join(reports_dir, pdf_name)
        try:
            branded = _brand_health_age_and_move_grok(
                html_report, getattr(report, 'ai_recommendations', None)
            )
            if save_report_pdf(branded or html_report, pdf_path):
                report.pdf_filename = pdf_name
                return True
            print(f'[Root Cause] PDF create returned errors for report {report.id}')
        except Exception as exc:
            print(f'[Root Cause] PDF save exception for report {report.id}: {exc}')
            traceback.print_exc()
        return False

    helpers['_save_pdf_for_report'] = _save_pdf_for_report
    if mod is not None:
        setattr(mod, '_save_pdf_for_report', _save_pdf_for_report)

    app.view_functions['view_report'] = view_report
    app.view_functions['download_report_pdf'] = download_report_pdf

    # Wrap admin so large scan uploads never return a raw 500 page
    _orig_admin = app.view_functions.get('admin')
    if _orig_admin is not None:
        def admin_safe(*args, **kwargs):
            try:
                return _orig_admin(*args, **kwargs)
            except Exception as exc:
                print(f'[Root Cause] admin fatal: {exc}')
                traceback.print_exc()
                flash(
                    f'Report generation failed: {type(exc).__name__}: {exc}. '
                    f'If you uploaded large imaging PDFs (hundreds of pages), try uploading '
                    f'one file at a time, or use the smaller text-based Full Scan PDFs.',
                    'error',
                )
                try:
                    return redirect(url_for('admin'))
                except Exception:
                    raise
        app.view_functions['admin'] = admin_safe

    print('[Root Cause] Applied ownership fix + Health Age + resilient PDF + admin safety')
