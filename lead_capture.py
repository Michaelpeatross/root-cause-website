"""Free on-site lead form. No third-party widget.

A visitor leaves a name, email, and phone. The site emails and texts the owner
right away so they can reply while the person is still on the page.
"""
import json
import os
import re
import time

_HITS = {}


def _digits(value):
    return re.sub(r'\D+', '', value or '')


def _clean_phone(value):
    digits = _digits(value)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) != 10:
        return ''
    return '+1' + digits


def _clean_email(value):
    text = (value or '').strip()[:120]
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
        return ''
    return text


def _limited(ip):
    now = time.time()
    hits = [stamp for stamp in _HITS.get(ip, []) if now - stamp < 3600]
    if len(hits) >= 5:
        _HITS[ip] = hits
        return True
    hits.append(now)
    _HITS[ip] = hits
    return False


def _store(row):
    try:
        from persistent_storage import setup_persistent_paths
        base = setup_persistent_paths(os.path.dirname(os.path.abspath(__file__))).get('data_dir')
    except Exception:
        base = None
    folder = base or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'leads.jsonl')
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row) + '\n')


def _notify(name, email, phone, note, source):
    admin_email = os.environ.get('ADMIN_EMAIL', 'michaelpeatross@gmail.com')
    admin_phone = os.environ.get('ADMIN_PHONE', '')
    subject = 'Root Cause lead: %s' % name
    body = (
        'Someone just asked for a callback on %s.\n\n'
        'Name: %s\nEmail: %s\nPhone: %s\nNote: %s\n\n'
        'Reply while they may still be on the site.'
    ) % (source, name, email, phone, note or '(none)')
    email_ok = False
    sms_ok = False
    try:
        from email_service import send_plain_email
        email_ok, _msg = send_plain_email(
            admin_email, subject, body, from_email='Info@root-cause-test.com'
        )
    except Exception as exc:
        print('[Root Cause] lead email failed: %s' % exc)
    if admin_phone:
        try:
            from notification_service import send_sms
            sms_ok, _msg = send_sms(
                admin_phone,
                'Root Cause lead: %s %s %s. %s' % (name, phone, email, (note or '')[:120]),
            )
        except Exception as exc:
            print('[Root Cause] lead sms failed: %s' % exc)
    return email_ok, sms_ok


WIDGET = '''
<div id="rc-lead">
  <button type="button" id="rc-lead-open">Get a callback</button>
  <form id="rc-lead-card" hidden>
    <strong>Want a call or text back?</strong>
    <p>Leave your name and number. We text the owner right away. Free, and it stays on this site.</p>
    <label>Name<input name="name" required maxlength="80" autocomplete="name"></label>
    <label>Email<input name="email" type="email" required maxlength="120" autocomplete="email"></label>
    <label>Phone<input name="phone" type="tel" required maxlength="20" autocomplete="tel"></label>
    <label>What do you need?<textarea name="note" maxlength="400" rows="2"></textarea></label>
    <input name="company" tabindex="-1" autocomplete="off" class="rc-lead-hp" aria-hidden="true">
    <button type="submit">Send</button>
    <button type="button" id="rc-lead-close">Close</button>
    <p id="rc-lead-status"></p>
  </form>
</div>
<style>
#rc-lead{position:fixed;left:16px;bottom:78px;z-index:2147483645;font-family:system-ui,sans-serif}
#rc-lead-open{background:#1b4332;color:#fff;border:0;border-radius:999px;padding:11px 15px;font-weight:700;box-shadow:0 8px 18px rgba(0,0,0,.22)}
#rc-lead-card{position:absolute;left:0;bottom:52px;width:min(320px,calc(100vw - 32px));background:#fff;color:#14241d;border:1px solid #d7e3dc;border-radius:14px;padding:12px;box-shadow:0 12px 30px rgba(0,0,0,.18);display:grid;gap:.45rem}
#rc-lead-card[hidden]{display:none}
#rc-lead-card p{margin:0;font-size:.85rem;color:#3d5349}
#rc-lead-card label{display:grid;gap:.15rem;font-size:.8rem;font-weight:700}
#rc-lead-card input,#rc-lead-card textarea{font:inherit;font-weight:400;padding:.45rem .55rem;border:1px solid #c9d7d0;border-radius:8px}
#rc-lead-card button{border:0;border-radius:999px;padding:.55rem .8rem;font-weight:700}
#rc-lead-card button[type="submit"]{background:#1b4332;color:#fff}
#rc-lead-close{background:#eef3f0;color:#14241d}
.rc-lead-hp{position:absolute;left:-9999px;height:0;width:0;opacity:0}
@media(max-width:600px){#rc-lead{left:auto;right:12px;bottom:84px;transition:opacity .2s}#rc-lead-open{padding:8px 12px;font-size:.8rem;min-height:36px}#rc-lead-card{left:auto;right:0;bottom:44px}#rc-lead.rc-hide{opacity:0;pointer-events:none}}
</style>
<script>
(function () {
  var root = document.getElementById('rc-lead');
  if (!root) return;
  var card = document.getElementById('rc-lead-card');
  var status = document.getElementById('rc-lead-status');
  function hide() { root.classList.toggle('rc-hide', window.innerWidth <= 600 && window.scrollY < 700 && card.hidden); }
  hide(); window.addEventListener('scroll', hide, {passive:true}); window.addEventListener('resize', hide);
  document.getElementById('rc-lead-open').addEventListener('click', function () { card.hidden = false; });
  document.getElementById('rc-lead-close').addEventListener('click', function () { card.hidden = true; });
  card.addEventListener('submit', function (evt) {
    evt.preventDefault();
    var data = {
      name: card.name.value, email: card.email.value, phone: card.phone.value,
      note: card.note.value, company: card.company.value, source: location.pathname
    };
    status.textContent = 'Sending…';
    fetch('/api/site-lead', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)})
      .then(function (r) { return r.json(); })
      .then(function (res) {
        status.textContent = (res && res.message) || 'Sent.';
        if (res && res.ok) card.reset();
      })
      .catch(function () { status.textContent = 'Could not send. Use the Contact page instead.'; });
  });
})();
</script>
'''


def register_lead_capture(app):
    from flask import jsonify, request

    @app.route('/api/site-lead', methods=['POST'])
    def api_site_lead():
        data = request.get_json(silent=True) or request.form or {}
        if (data.get('company') or '').strip():
            return jsonify({'ok': True, 'message': 'Thanks. We have it.'})
        name = re.sub(r'\s+', ' ', (data.get('name') or '').strip())[:80]
        email = _clean_email(data.get('email'))
        phone = _clean_phone(data.get('phone'))
        note = re.sub(r'\s+', ' ', (data.get('note') or '').strip())[:400]
        source = re.sub(r'[^a-z0-9/_-]+', '', (data.get('source') or 'site').lower())[:80] or 'site'
        if len(name) < 2 or not email or not phone:
            return jsonify({'ok': False, 'message': 'Enter your name, a real email, and a 10-digit phone number.'})
        ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or 'unknown').split(',')[0].strip()
        if _limited(ip):
            return jsonify({'ok': False, 'message': 'Too many notes from this connection. Email Info@root-cause-test.com.'})
        row = {'name': name, 'email': email, 'phone': phone, 'note': note, 'source': source, 'at': int(time.time())}
        try:
            _store(row)
        except Exception as exc:
            print('[Root Cause] lead store failed: %s' % exc)
        _notify(name, email, phone, note, source)
        return jsonify({'ok': True, 'message': 'Thanks, %s. We got it and will text you back.' % name.split()[0]})

    orig_contact = app.view_functions.get('contact')

    def contact_with_ping():
        resp = orig_contact()
        if request.method == 'POST':
            phone = _clean_phone(request.form.get('phone'))
            note = re.sub(r'\s+', ' ', (request.form.get('message') or '').strip())[:400]
            name = re.sub(r'\s+', ' ', (request.form.get('name') or 'Website visitor').strip())[:80] or 'Website visitor'
            email = _clean_email(request.form.get('email')) or 'not given'
            if phone and note:
                _notify(name, email, phone, note, 'contact page')
        return resp

    if orig_contact:
        app.view_functions['contact'] = contact_with_ping

    @app.after_request
    def _lead_widget(resp):
        try:
            path = request.path or ''
            if path.startswith('/admin') or path.startswith('/api/'):
                return resp
            if path.rstrip('/') == '/k12-scholarships':
                return resp  # coming-soon nonprofit page: no Root Cause callback form
            if 'html' not in (resp.headers.get('Content-Type') or ''):
                return resp
            data = resp.get_data(as_text=True)
            if not data or 'id="rc-lead"' in data or '</body>' not in data:
                return resp
            if 'site-header' not in data and '<body' not in data:
                return resp
            resp.set_data(data.replace('</body>', WIDGET + '</body>', 1))
        except Exception:
            pass
        return resp
