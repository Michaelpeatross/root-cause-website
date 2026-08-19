"""Live upgrades: Health Age at top, Grok analysis near top, on-demand PDF."""
import os
import re


def _brand_health_age_and_move_grok(html, ai_html=None):
    """Rename overall score to Health Age and move Grok analysis under it."""
    if not html:
        return html or ''

    # Brand overall card as Health Age
    html = html.replace('Your Overall Health Score', 'Your Health Age')
    html = html.replace('>Overall Health Score<', '>Your Health Age<')
    html = re.sub(
        r'(Previous\s+)(\d+\s*→)',
        r'\1Health Age \2',
        html,
        count=3,
    )

    # Prefer injected AI HTML; otherwise try to extract an existing AI block from the page
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
            r'(<div class="health-overall-card[\s\S]*?</div>\s*</div>\s*<div class="health-score-scale">[\s\S]*?</div>\s*</div>)',
            html,
        )
        if not card_end:
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
    _user_owns_report = helpers['_user_owns_report']
    _report_has_substantive_html = helpers['_report_has_substantive_html']
    _client_display_name = helpers['_client_display_name']
    _prefer_full_scan_template = helpers['_prefer_full_scan_template']

    def _rebuild_html_with_scores(report):
        """Rebuild report HTML so Health Age + scores appear; persist on the report."""
        html = report.generated_report or report.original_generated_report or ''
        needs = (
            'health-overall-card' not in html
            or 'Your Health Age' not in html
        )
        if not (report.raw_data or '').strip():
            branded = _brand_health_age_and_move_grok(html, report.ai_recommendations)
            if branded != html:
                report.generated_report = branded
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return branded
            return html

        if needs:
            try:
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
            except Exception as exc:
                print(f'[Root Cause] Health Age rebuild failed for report {report.id}: {exc}')
                import traceback
                traceback.print_exc()

        html = _brand_health_age_and_move_grok(html, report.ai_recommendations)
        if html and len(html) > 200:
            report.generated_report = html
            if not report.original_generated_report or 'Your Health Age' not in (report.original_generated_report or ''):
                report.original_generated_report = html
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
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
            branded = _brand_health_age_and_move_grok(html_report, getattr(report, 'ai_recommendations', None))
            if save_report_pdf(branded or html_report, pdf_path):
                report.pdf_filename = pdf_name
                return True
            print(f'[Root Cause] PDF create returned errors for report {report.id}')
        except Exception as exc:
            print(f'[Root Cause] PDF save exception for report {report.id}: {exc}')
        return False

    helpers['_save_pdf_for_report'] = _save_pdf_for_report
    if mod is not None:
        setattr(mod, '_save_pdf_for_report', _save_pdf_for_report)

    print('[Root Cause] Applied Health Age + Grok top + PDF live upgrades')
