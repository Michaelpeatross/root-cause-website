"""Self-service account deletion (Apple App Store Review Guideline 5.1.1(v)).

Signed-in users can permanently delete their account and data from inside
the app/site at /account/delete. Registered from app.py after the main app
is loaded, using the same models the admin "delete_user" action uses.
"""
import os

CONFIRM_WORD = 'DELETE'

PAGE = """{% extends "base.html" %}
{% block title %}Delete account | Root Cause Test{% endblock %}
{% block content %}
<div class="container" style="max-width:640px;margin:2rem auto;">
  <h1>Delete your account</h1>
  {% if error %}<div class="status-banner err" style="background:#fdecea;color:#7a1f16;padding:.75rem 1rem;border-radius:10px;">{{ error }}</div>{% endif %}
  <p>This permanently deletes your Root Cause account for <strong>{{ email }}</strong> and everything tied to it:</p>
  <ul>
    <li>Your login, name and phone number</li>
    <li>Food scan history and nutrition log</li>
    <li>Wellness reports, uploaded documents and scan files</li>
  </ul>
  <p>This cannot be undone. Payment records kept by Stripe for tax and accounting are not stored by us and are not affected.</p>
  <form method="POST">
    <label for="password">Password</label>
    <input type="password" id="password" name="password" autocomplete="current-password" required>
    <label for="confirm">Type {{ confirm_word }} to confirm</label>
    <input type="text" id="confirm" name="confirm" autocomplete="off" required>
    <p style="margin-top:1rem;"><button class="btn btn-primary" type="submit" style="background:#b03a2e;border-color:#b03a2e;">Permanently delete my account</button>
    <a class="btn btn-outline" href="/dashboard">Cancel</a></p>
  </form>
  <p class="hint">Trouble signing in? Email Info@root-cause-test.com from your account email and we will delete it for you.</p>
</div>
{% endblock %}"""

DONE = """{% extends "base.html" %}
{% block title %}Account deleted | Root Cause Test{% endblock %}
{% block content %}
<div class="container" style="max-width:640px;margin:2rem auto;">
  <h1>Your account has been deleted</h1>
  <p>Your account and saved data were permanently removed. You can keep using the Food Scanner as a guest.</p>
  <p><a class="btn btn-primary" href="/food-scanner">Open Food Scanner</a></p>
</div>
{% endblock %}"""


def _remove_file(*parts):
    try:
        path = os.path.join(*parts)
        if path and os.path.isfile(path):
            os.remove(path)
    except Exception as exc:
        print('[AccountDelete] file remove skipped:', exc)


def delete_account_data(email, db, User, Report=None, ClientDocument=None, ReportScanPdf=None,
                        documents_dir=None, reports_dir=None):
    """Delete every DB row and stored file tied to this email. Returns True if a user row was removed."""
    email = (email or '').strip().lower()
    if not email:
        return False
    if ClientDocument is not None:
        for doc in ClientDocument.query.filter_by(user_email=email).all():
            if documents_dir and doc.stored_filename:
                _remove_file(documents_dir, doc.stored_filename)
        ClientDocument.query.filter_by(user_email=email).delete(synchronize_session=False)
    if Report is not None:
        report_ids = [r.id for r in Report.query.filter_by(user_email=email).all()]
        if ReportScanPdf is not None and report_ids:
            for pdf in ReportScanPdf.query.filter(ReportScanPdf.report_id.in_(report_ids)).all():
                if documents_dir and pdf.stored_filename:
                    _remove_file(documents_dir, pdf.stored_filename)
            ReportScanPdf.query.filter(ReportScanPdf.report_id.in_(report_ids)).delete(synchronize_session=False)
        for rep in Report.query.filter_by(user_email=email).all():
            if reports_dir and getattr(rep, 'pdf_filename', None):
                _remove_file(reports_dir, rep.pdf_filename)
        Report.query.filter_by(user_email=email).delete(synchronize_session=False)
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user is not None:
        db.session.delete(user)
    db.session.commit()
    for mod, fn in (('food_scan_history', 'delete_history'), ('food_diary', 'delete_meals')):
        try:
            getattr(__import__(mod), fn)(email)
        except Exception as exc:
            print('[AccountDelete] %s skipped: %s' % (mod, exc))
    return user is not None


def register_account_deletion_routes(app, db, User, Report=None, ClientDocument=None, ReportScanPdf=None,
                                     documents_dir=None, reports_dir=None):
    from flask import render_template_string, request, session, redirect
    from werkzeug.security import check_password_hash

    def _current_user():
        uid = session.get('user_id')
        if not uid:
            return None
        try:
            return db.session.get(User, uid)
        except Exception:
            return User.query.get(uid)

    def account_delete():
        user = _current_user()
        if not user:
            return redirect('/login?next=/account/delete')
        error = ''
        if request.method == 'POST':
            password = request.form.get('password') or ''
            confirm = (request.form.get('confirm') or '').strip().upper()
            if confirm != CONFIRM_WORD:
                error = 'Type %s to confirm.' % CONFIRM_WORD
            elif not (user.password and check_password_hash(user.password, password)):
                error = 'That password is not correct.'
            elif getattr(user, 'is_admin', False):
                error = 'Admin accounts cannot be deleted here.'
            else:
                email = user.email
                delete_account_data(email, db, User, Report, ClientDocument, ReportScanPdf, documents_dir, reports_dir)
                session.clear()
                print('[AccountDelete] account deleted by user request')
                return render_template_string(DONE)
        return render_template_string(PAGE, email=user.email, error=error, confirm_word=CONFIRM_WORD)

    if '/account/delete' not in {r.rule for r in app.url_map.iter_rules()}:
        app.add_url_rule('/account/delete', 'account_delete_self', account_delete, methods=['GET', 'POST'])

    @app.after_request
    def _account_delete_link(response):
        # Surface the delete option on the signed-in dashboard (App Store requires it be easy to find).
        try:
            if request.path == '/dashboard' and 'text/html' in (response.headers.get('Content-Type') or ''):
                html = response.get_data(as_text=True)
                anchor = 'Your personalized bioenergetic portal</p>'
                if html and 'href="/account/delete"' not in html:
                    card = ('<div class="card" style="margin:1rem 0;"><h2>Account</h2>'
                            '<p><a href="/account/delete">Delete my account and data</a></p></div>')
                    # Keep account deletion at the bottom of the portal, not under the welcome line.
                    end = html.rfind('</div>')
                    if end != -1:
                        html = html[:end] + card + html[end:]
                    elif '</body>' in html:
                        html = html.replace('</body>', card + '</body>', 1)
                    elif anchor in html:
                        html = html.replace(anchor, anchor + card, 1)
                    response.set_data(html)
        except Exception as exc:
            print('[AccountDelete] dashboard link skipped:', exc)
        return response

    print('[Root Cause] Registered /account/delete')
