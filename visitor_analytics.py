"""First-party, privacy-friendly visitor analytics for Root Cause Test.

* Server-side page-view logging for real HTML GET pages (skips static, /api, /admin,
  bots, health checks, prefetches). No outside accounts needed.
* Anonymous first-party cookies: ``rc_vid`` (random visitor id, 1 year) and
  ``rc_sid`` (session id, 30-minute sliding window).
* IP addresses are never stored. Only a salted, daily-rotating hash is kept so the
  same IP cannot be linked across days.
* Funnel events: order page views, checkout clicks / Stripe redirects, checkout
  success, Food Scanner use, contact / signup submits.
* Optional tiny JS beacon adds timezone, screen size and engaged seconds.
* Writes go through a background queue into a separate SQLite file on the same
  persistent disk as the main database, so logging can never slow or break a page.
* Private dashboard at /admin/stats (admin login) + JSON at /admin/stats.json
  (admin login or ANALYTICS_API_TOKEN bearer token).
* Env-driven third-party tags (GA4, Clarity, Search Console, Bing) exposed to
  templates as ``rc_tags``.
"""

import hashlib
import hmac
import json
import os
import queue
import re
import secrets
import threading
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
    CENTRAL = ZoneInfo('America/Chicago')
except Exception:  # pragma: no cover
    CENTRAL = None

_HERE = os.path.dirname(os.path.abspath(__file__))

VISITOR_COOKIE = 'rc_vid'
SESSION_COOKIE = 'rc_sid'
INTERNAL_COOKIE = 'rc_internal'
VISITOR_MAX_AGE = 365 * 24 * 3600
SESSION_MAX_AGE = 30 * 60

SKIP_PREFIXES = (
    '/static', '/api/', '/admin', '/.well-known', '/twilio', '/download/',
    '/og-', '/reports/', '/documents/',
)
SKIP_EXACT = {
    '/favicon.ico', '/robots.txt', '/sitemap.xml', '/manifest.json', '/sw.js',
    '/health', '/healthz', '/healthcheck', '/ping', '/status', '/logout',
}
# Pages where third-party tags (GA4 / Clarity) are never loaded: signed-in or
# health-data screens.
PRIVATE_PREFIXES = (
    '/admin', '/dashboard', '/reports', '/documents', '/account', '/nutrition',
    '/checkout/success', '/login', '/register',
)
APEXFORGE_PATHS = ('/agency', '/apexforge', '/business', '/ai-transformation')
FOAM_PATHS = ('/foam', '/spray-foam')
ORDER_PATHS = ('/buy',)
SCANNER_PATHS = ('/scan-food', '/food-scanner')
FOOD_SCAN_API = re.compile(r'^/api/food-scan/(barcode|search|photo|meal/save|meal/item|meal)/?$')

BOT_RE = re.compile(
    r'bot\b|bot/|crawl|spider|slurp|archiver|facebookexternalhit|facebot|embedly|'
    r'quora link|preview|whatsapp|telegram|discord|slack|skype|vkshare|bitly|'
    r'curl|wget|python|httpx|aiohttp|go-http|java/|okhttp|libwww|perl|ruby|php|'
    r'node-fetch|axios|undici|headless|phantom|selenium|puppeteer|playwright|'
    r'lighthouse|pagespeed|gtmetrix|pingdom|uptime|monitor|statuscake|datadog|'
    r'newrelic|\brender\b|scanner|check|validator|feedfetcher|\brss\b|ahrefs|semrush|'
    r'mj12|dotbot|petal|bytespider|gptbot|chatgpt-user|oai-searchbot|claude|anthropic|'
    r'perplexity|ccbot|applebot|yandex|baidu|sogou|exabot|seznam|duckduck|bingpreview|'
    r'google-inspectiontool|googleother|amazonbot|meta-externalagent|cohere|diffbot|'
    r'ia_archiver|zgrab|masscan|nmap|nikto|sqlmap|httpclient|winhttp',
    re.I,
)
BOT_NAMES = (
    ('googlebot', 'Googlebot'), ('google-inspectiontool', 'Google Inspection'),
    ('googleother', 'GoogleOther'), ('adsbot-google', 'Google AdsBot'),
    ('bingbot', 'Bingbot'), ('bingpreview', 'Bing Preview'), ('applebot', 'Applebot'),
    ('duckduck', 'DuckDuckBot'), ('yandex', 'Yandex'), ('baidu', 'Baidu'),
    ('gptbot', 'GPTBot (OpenAI)'), ('oai-searchbot', 'OAI-SearchBot'),
    ('chatgpt-user', 'ChatGPT-User'), ('claude', 'Claude'), ('anthropic', 'Anthropic'),
    ('perplexity', 'Perplexity'), ('ccbot', 'CommonCrawl'), ('bytespider', 'Bytespider'),
    ('amazonbot', 'Amazonbot'), ('meta-externalagent', 'Meta AI'),
    ('facebookexternalhit', 'Facebook preview'), ('facebot', 'Facebook'),
    ('twitterbot', 'X/Twitter preview'), ('linkedinbot', 'LinkedIn preview'),
    ('slack', 'Slack preview'), ('discord', 'Discord preview'),
    ('whatsapp', 'WhatsApp preview'), ('telegram', 'Telegram preview'),
    ('ahrefs', 'Ahrefs'), ('semrush', 'Semrush'), ('mj12', 'Majestic'),
    ('dotbot', 'Moz DotBot'), ('petal', 'PetalBot'), ('lighthouse', 'Lighthouse'),
    ('pagespeed', 'PageSpeed'), ('uptime', 'Uptime monitor'), ('pingdom', 'Pingdom'),
    ('render', 'Render health check'), ('curl', 'curl'), ('wget', 'wget'),
    ('python', 'Python script'), ('go-http', 'Go client'), ('headless', 'Headless browser'),
)

SOURCE_DOMAINS = (
    (('t.co', 'x.com', 'twitter.com', 'mobile.twitter.com', 'mobile.x.com'), 'x', 'social'),
    (('facebook.com', 'm.facebook.com', 'l.facebook.com', 'lm.facebook.com', 'fb.com', 'fb.me'), 'facebook', 'social'),
    (('instagram.com', 'l.instagram.com'), 'instagram', 'social'),
    (('linkedin.com', 'lnkd.in'), 'linkedin', 'social'),
    (('reddit.com', 'old.reddit.com', 'out.reddit.com'), 'reddit', 'social'),
    (('youtube.com', 'm.youtube.com', 'youtu.be'), 'youtube', 'social'),
    (('tiktok.com',), 'tiktok', 'social'),
    (('pinterest.com', 'pin.it'), 'pinterest', 'social'),
    (('threads.net',), 'threads', 'social'),
    (('bsky.app',), 'bluesky', 'social'),
    (('bing.com', 'cn.bing.com'), 'bing', 'search'),
    (('duckduckgo.com',), 'duckduckgo', 'search'),
    (('search.yahoo.com', 'yahoo.com'), 'yahoo', 'search'),
    (('search.brave.com',), 'brave', 'search'),
    (('ecosia.org',), 'ecosia', 'search'),
    (('chatgpt.com', 'chat.openai.com'), 'chatgpt', 'ai'),
    (('perplexity.ai',), 'perplexity', 'ai'),
    (('grok.com',), 'grok', 'ai'),
    (('gemini.google.com',), 'gemini', 'ai'),
    (('claude.ai',), 'claude', 'ai'),
    (('copilot.microsoft.com',), 'copilot', 'ai'),
    (('checkout.stripe.com', 'buy.stripe.com'), 'stripe', 'internal'),
)
UTM_SOURCE_ALIASES = {'twitter': 'x', 'x.com': 'x', 't.co': 'x', 'fb': 'facebook', 'ig': 'instagram'}
OWN_HOSTS = ('root-cause-test.com', 'www.root-cause-test.com', 'localhost', '127.0.0.1')

# Public (non-secret) tag IDs. An env var of the same name overrides the code
# default; set the env var to "off" to disable a tag without a code change.
# Add future IDs here so they work without touching Render env vars.
TAG_DEFAULTS = {
    'GA_MEASUREMENT_ID': 'G-HTF90RE438',
    'CLARITY_PROJECT_ID': 'ytak3q6nb0',
    'GOOGLE_SITE_VERIFICATION': '',
    'BING_SITE_VERIFICATION': '',
}


def _tag_value(name):
    env = (os.environ.get(name) or '').strip()
    if env.lower() in ('off', 'none', 'disabled', '0', 'false'):
        return ''
    return env or TAG_DEFAULTS.get(name, '')


_GA_RE = re.compile(r'^G-[A-Z0-9]{4,20}$')
_CLARITY_RE = re.compile(r'^[a-z0-9]{5,20}$')
_VERIFY_RE = re.compile(r'^[A-Za-z0-9_\-=.:+/]{5,200}$')
_ID_RE = re.compile(r'^[a-f0-9]{16,32}$')
_UUID_RE = re.compile(r'^[a-f0-9]{32}$')

_TZ_COUNTRY = {}


def _load_tz_country():
    if _TZ_COUNTRY:
        return _TZ_COUNTRY
    for path in ('/usr/share/zoneinfo/zone.tab',):
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                for line in fh:
                    if line.startswith('#'):
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 3:
                        _TZ_COUNTRY[parts[2]] = parts[0]
        except Exception:
            pass
    for tz in ('America/Chicago', 'America/New_York', 'America/Denver', 'America/Los_Angeles',
               'America/Phoenix', 'America/Anchorage', 'Pacific/Honolulu', 'America/Detroit',
               'America/Indiana/Indianapolis', 'America/Boise'):
        _TZ_COUNTRY.setdefault(tz, 'US')
    _TZ_COUNTRY.setdefault('US/Central', 'US')
    _TZ_COUNTRY.setdefault('US/Eastern', 'US')
    _TZ_COUNTRY.setdefault('US/Pacific', 'US')
    _TZ_COUNTRY.setdefault('US/Mountain', 'US')
    return _TZ_COUNTRY


# ---------------------------------------------------------------------------
# Small parsers
# ---------------------------------------------------------------------------

def central_now():
    if CENTRAL is not None:
        return datetime.now(CENTRAL)
    return datetime.now(timezone.utc) - timedelta(hours=5)


def is_bot(ua):
    ua = (ua or '').strip()
    if len(ua) < 12:
        return True
    return bool(BOT_RE.search(ua))


def bot_name(ua):
    low = (ua or '').lower()
    if not low.strip():
        return 'Empty user agent'
    for needle, name in BOT_NAMES:
        if needle in low:
            return name
    return 'Other bot'


def parse_ua(ua):
    ua = ua or ''
    low = ua.lower()
    if 'ipad' in low or 'tablet' in low or ('android' in low and 'mobile' not in low):
        device = 'tablet'
    elif 'mobi' in low or 'iphone' in low or 'ipod' in low or 'android' in low:
        device = 'mobile'
    else:
        device = 'desktop'

    if 'fban' in low or 'fbav' in low or 'fb_iab' in low:
        browser = 'Facebook in-app'
    elif 'instagram' in low:
        browser = 'Instagram in-app'
    elif 'twitter' in low or 'twitterandroid' in low:
        browser = 'X in-app'
    elif 'linkedinapp' in low:
        browser = 'LinkedIn in-app'
    elif ' gsa/' in low:
        browser = 'Google app'
    elif 'edg/' in low or 'edga/' in low or 'edgios/' in low:
        browser = 'Edge'
    elif 'opr/' in low or 'opera' in low:
        browser = 'Opera'
    elif 'samsungbrowser' in low:
        browser = 'Samsung Internet'
    elif 'duckduckgo' in low:
        browser = 'DuckDuckGo'
    elif 'crios' in low:
        browser = 'Chrome'
    elif 'fxios' in low or 'firefox/' in low:
        browser = 'Firefox'
    elif 'chrome/' in low or 'chromium' in low:
        browser = 'Chrome'
    elif 'safari/' in low:
        browser = 'Safari'
    else:
        browser = 'Other'

    if 'iphone' in low or 'ipad' in low or 'ipod' in low:
        os_name = 'iOS'
    elif 'android' in low:
        os_name = 'Android'
    elif 'windows' in low:
        os_name = 'Windows'
    elif 'cros' in low:
        os_name = 'ChromeOS'
    elif 'mac os x' in low or 'macintosh' in low:
        os_name = 'macOS'
    elif 'linux' in low:
        os_name = 'Linux'
    else:
        os_name = 'Other'
    return device, browser, os_name


def referrer_domain(referrer):
    if not referrer:
        return ''
    try:
        host = (urlparse(referrer).hostname or '').lower()
    except Exception:
        return ''
    return host[4:] if host.startswith('www.') else host


def classify_source(ref_domain, utm_source='', request_host=''):
    """Return (source, channel)."""
    utm = (utm_source or '').strip().lower()
    if utm:
        utm = UTM_SOURCE_ALIASES.get(utm, utm)
        return utm[:60], 'campaign'
    if not ref_domain:
        return 'direct', 'direct'
    own = {h[4:] if h.startswith('www.') else h for h in OWN_HOSTS}
    rh = (request_host or '').split(':')[0].lower()
    if rh:
        own.add(rh[4:] if rh.startswith('www.') else rh)
    if ref_domain in own:
        return 'internal', 'internal'
    for domains, name, channel in SOURCE_DOMAINS:
        for d in domains:
            if ref_domain == d or ref_domain.endswith('.' + d):
                return name, channel
    if re.match(r'^(.+\.)?google\.[a-z.]+$', ref_domain) or ref_domain.startswith('google.'):
        return 'google', 'search'
    if 'android-app://com.google' in ref_domain:
        return 'google', 'search'
    return ref_domain[:60], 'referral'


def site_section(path):
    for p in APEXFORGE_PATHS:
        if path == p or path.startswith(p + '/'):
            return 'apexforge'
    for p in FOAM_PATHS:
        if path == p or path.startswith(p + '/'):
            return 'foam'
    return 'rootcause'


def _header_country(headers):
    for name in ('CF-IPCountry', 'X-Country-Code', 'X-Vercel-IP-Country',
                 'CloudFront-Viewer-Country', 'X-Geo-Country', 'X-Render-Country'):
        val = (headers.get(name) or '').strip().upper()
        if re.match(r'^[A-Z]{2}$', val) and val not in ('XX', 'T1'):
            return val
    return ''


def _client_ip(request):
    for name in ('CF-Connecting-IP', 'True-Client-IP'):
        val = (request.headers.get(name) or '').strip()
        if val:
            return val
    xff = request.headers.get('X-Forwarded-For') or ''
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr or ''


def _short_lang(accept_language):
    first = (accept_language or '').split(',')[0].split(';')[0].strip()
    return first[:16]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class AnalyticsStore(object):
    def __init__(self, db_url, salt_path=None):
        from sqlalchemy import (
            MetaData, Table, Column, Integer, String, DateTime, Boolean, Text, Index,
            create_engine, event,
        )
        self.db_url = db_url
        kwargs = {}
        if db_url.startswith('sqlite'):
            kwargs['connect_args'] = {'timeout': 15, 'check_same_thread': False}
        self.engine = create_engine(db_url, **kwargs)
        if db_url.startswith('sqlite'):
            @event.listens_for(self.engine, 'connect')
            def _pragmas(dbapi_conn, _rec):  # pragma: no cover - trivial
                try:
                    cur = dbapi_conn.cursor()
                    cur.execute('PRAGMA journal_mode=WAL')
                    cur.execute('PRAGMA synchronous=NORMAL')
                    cur.close()
                except Exception:
                    pass

        meta = MetaData()
        self.events = Table(
            'rc_visit_event', meta,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('eid', String(32), nullable=False),
            Column('ts', DateTime, nullable=False),
            Column('day', String(10), nullable=False),
            Column('kind', String(10), nullable=False),
            Column('name', String(40), nullable=False),
            Column('site', String(16)),
            Column('path', String(300)),
            Column('status', Integer),
            Column('referrer', String(500)),
            Column('ref_domain', String(120)),
            Column('source', String(60)),
            Column('channel', String(20)),
            Column('utm_source', String(100)),
            Column('utm_medium', String(100)),
            Column('utm_campaign', String(150)),
            Column('utm_term', String(150)),
            Column('utm_content', String(150)),
            Column('country', String(8)),
            Column('country_src', String(8)),
            Column('lang', String(16)),
            Column('device', String(10)),
            Column('browser', String(40)),
            Column('os', String(30)),
            Column('visitor_id', String(36)),
            Column('session_id', String(36)),
            Column('new_visitor', Boolean),
            Column('new_session', Boolean),
            Column('ip_hash', String(24)),
            Column('logged_in', Boolean),
            Column('internal', Boolean),
            Column('tz', String(64)),
            Column('screen', String(16)),
            Column('engaged_sec', Integer),
            Column('js', Boolean),
            Column('meta', Text),
        )
        Index('ix_rc_visit_event_eid', self.events.c.eid, unique=True)
        Index('ix_rc_visit_event_day', self.events.c.day)
        Index('ix_rc_visit_event_visitor', self.events.c.visitor_id)
        self.bots = Table(
            'rc_bot_daily', meta,
            Column('day', String(10), primary_key=True),
            Column('bot', String(40), primary_key=True),
            Column('hits', Integer, nullable=False, default=0),
        )
        self.meta = meta
        meta.create_all(self.engine)
        self._salt_secret = self._load_salt(salt_path)
        self._q = queue.Queue(maxsize=20000)
        self._thread = None
        self._pid = None
        self._lock = threading.Lock()
        self.dropped = 0
        self.errors = 0
        self.last_error = ''
        self.sync = os.environ.get('RC_ANALYTICS_SYNC') == '1'

    # -- salt ----------------------------------------------------------
    @staticmethod
    def _load_salt(salt_path):
        env = (os.environ.get('ANALYTICS_SALT') or '').strip()
        if env:
            return env
        if salt_path:
            try:
                if os.path.isfile(salt_path):
                    with open(salt_path, 'r', encoding='utf-8') as fh:
                        val = fh.read().strip()
                    if len(val) >= 32:
                        return val
                val = secrets.token_hex(32)
                os.makedirs(os.path.dirname(salt_path), exist_ok=True)
                with open(salt_path, 'w', encoding='utf-8') as fh:
                    fh.write(val)
                try:
                    os.chmod(salt_path, 0o600)
                except Exception:
                    pass
                return val
            except Exception:
                pass
        return secrets.token_hex(32)  # process-local fallback

    def ip_hash(self, ip, day):
        if not ip:
            return ''
        key = hmac.new(self._salt_secret.encode(), day.encode(), hashlib.sha256).digest()
        return hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()[:20]

    # -- writer --------------------------------------------------------
    def _ensure_thread(self):
        if self.sync:
            return
        pid = os.getpid()
        if self._thread is not None and self._thread.is_alive() and self._pid == pid:
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive() and self._pid == pid:
                return
            self._q = queue.Queue(maxsize=20000) if self._pid not in (None, pid) else self._q
            self._pid = pid
            self._thread = threading.Thread(target=self._run, name='rc-analytics', daemon=True)
            self._thread.start()

    def submit(self, op):
        if self.sync:
            self._apply_batch([op])
            return
        try:
            self._ensure_thread()
            self._q.put_nowait(op)
        except queue.Full:
            self.dropped += 1
        except Exception as exc:  # pragma: no cover
            self.errors += 1
            self.last_error = str(exc)[:200]

    def _run(self):
        while True:
            try:
                op = self._q.get()
            except Exception:  # pragma: no cover
                time.sleep(0.5)
                continue
            batch = [op]
            while len(batch) < 200:
                try:
                    batch.append(self._q.get_nowait())
                except queue.Empty:
                    break
            try:
                self._apply_batch(batch)
            finally:
                for _ in batch:
                    try:
                        self._q.task_done()
                    except ValueError:
                        pass

    def _apply_batch(self, batch):
        try:
            with self.engine.begin() as conn:
                for op in batch:
                    self._apply(conn, op)
        except Exception:
            for op in batch:  # retry individually so one bad row can't sink the rest
                try:
                    with self.engine.begin() as conn:
                        self._apply(conn, op)
                except Exception as exc:
                    self.errors += 1
                    self.last_error = '%s: %s' % (type(exc).__name__, str(exc)[:200])
                    print('[Root Cause] analytics write skipped: %s' % self.last_error)

    def _apply(self, conn, op):
        kind = op[0]
        if kind == 'insert':
            conn.execute(self.events.insert().values(**op[1]))
        elif kind == 'update':
            eid, values = op[1], op[2]
            if values:
                conn.execute(self.events.update().where(self.events.c.eid == eid).values(**values))
        elif kind == 'engaged':
            from sqlalchemy import case
            eid, secs = op[1], op[2]
            col = self.events.c.engaged_sec
            conn.execute(
                self.events.update().where(self.events.c.eid == eid).values(
                    engaged_sec=case((col.is_(None), secs), (col < secs, secs), else_=col)
                )
            )
        elif kind == 'bot':
            day, name = op[1], op[2]
            res = conn.execute(
                self.bots.update().where(
                    (self.bots.c.day == day) & (self.bots.c.bot == name)
                ).values(hits=self.bots.c.hits + 1)
            )
            if not res.rowcount:
                conn.execute(self.bots.insert().values(day=day, bot=name, hits=1))
        elif kind == 'tzcountry':
            # tz-derived country only fills in when no header country exists.
            from sqlalchemy import or_
            c = self.events.c
            conn.execute(self.events.update().where(
                (c.eid == op[1]) & or_(c.country.is_(None), c.country == '')
            ).values(country=op[2], country_src='tz'))
        elif kind == 'prune':
            conn.execute(self.events.delete().where(self.events.c.day < op[1]))
            conn.execute(self.bots.delete().where(self.bots.c.day < op[1]))

    def flush(self, timeout=2.0):
        if self.sync:
            return True
        deadline = time.time() + timeout
        while time.time() < deadline:
            if getattr(self._q, 'unfinished_tasks', 0) == 0:
                return True
            time.sleep(0.02)
        return False

    # -- reads ---------------------------------------------------------
    def rows_since(self, day_from, limit=400000):
        from sqlalchemy import select
        cols = self.events.c
        stmt = (
            select(cols.ts, cols.day, cols.kind, cols.name, cols.site, cols.path, cols.status,
                   cols.referrer, cols.ref_domain, cols.source, cols.channel, cols.utm_source,
                   cols.utm_medium, cols.utm_campaign, cols.country, cols.lang, cols.device,
                   cols.browser, cols.os, cols.visitor_id, cols.session_id, cols.new_visitor,
                   cols.new_session, cols.ip_hash, cols.logged_in, cols.internal, cols.tz,
                   cols.screen, cols.engaged_sec, cols.js, cols.meta)
            .where(cols.day >= day_from)
            .order_by(cols.id.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(stmt)]

    def bot_rows_since(self, day_from):
        from sqlalchemy import select
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(
                select(self.bots.c.day, self.bots.c.bot, self.bots.c.hits).where(self.bots.c.day >= day_from)
            )]

    def visitor_summary(self, visitor_id):
        from sqlalchemy import select, func
        c = self.events.c
        with self.engine.connect() as conn:
            n = conn.execute(select(func.count()).where(
                (c.visitor_id == visitor_id) & (c.kind == 'pageview'))).scalar() or 0
            ev = conn.execute(select(func.count()).where(
                (c.visitor_id == visitor_id) & (c.kind == 'event'))).scalar() or 0
            last = conn.execute(select(c.ts, c.path, c.internal).where(
                (c.visitor_id == visitor_id) & (c.kind == 'pageview')).order_by(c.id.desc()).limit(1)).first()
        return n, ev, last

    def total_rows(self):
        from sqlalchemy import select, func
        with self.engine.connect() as conn:
            return conn.execute(select(func.count()).select_from(self.events)).scalar() or 0


# ---------------------------------------------------------------------------
# Aggregation for dashboard / JSON
# ---------------------------------------------------------------------------

def _top(counter, n=15):
    return [{'key': k, 'count': v} for k, v in counter.most_common(n)]


def _top_with_visitors(count_c, vis_map, n=15):
    out = []
    for k, v in count_c.most_common(n):
        out.append({'key': k, 'count': v, 'visitors': len(vis_map.get(k, ()))})
    return out


def build_stats(store, days=30, site='rootcause', include_internal=False):
    days = max(1, min(int(days or 30), 365))
    now_c = central_now()
    today = now_c.date()
    day_from_dt = today - timedelta(days=max(days, 30) - 1)
    day_from = day_from_dt.isoformat()
    rows = store.rows_since(day_from)
    if site and site != 'all':
        rows = [r for r in rows if (r.get('site') or 'rootcause') == site]
    if not include_internal:
        rows = [r for r in rows if not r.get('internal')]

    d_today = today.isoformat()
    d_7 = (today - timedelta(days=6)).isoformat()
    d_30 = (today - timedelta(days=29)).isoformat()
    d_period = (today - timedelta(days=days - 1)).isoformat()

    def period_summary(start):
        pv = [r for r in rows if r['kind'] == 'pageview' and r['day'] >= start]
        return {
            'pageviews': len(pv),
            'visitors': len({r['visitor_id'] for r in pv if r['visitor_id']}),
            'sessions': len({r['session_id'] for r in pv if r['session_id']}),
            'new_visitors': len({r['visitor_id'] for r in pv if r['new_visitor']}),
            'js_confirmed_visitors': len({r['visitor_id'] for r in pv if r['js']}),
        }

    summary = {
        'today': period_summary(d_today),
        '7d': period_summary(d_7),
        '30d': period_summary(d_30),
    }
    if days not in (1, 7, 30):
        summary['%dd' % days] = period_summary(d_period)

    prow = [r for r in rows if r['day'] >= d_period]
    pv = [r for r in prow if r['kind'] == 'pageview']
    ev = [r for r in prow if r['kind'] == 'event']

    # Daily series
    daily = []
    by_day_pv = Counter(r['day'] for r in pv)
    by_day_vis = defaultdict(set)
    for r in pv:
        if r['visitor_id']:
            by_day_vis[r['day']].add(r['visitor_id'])
    by_day_ck = Counter(r['day'] for r in ev if r['name'] == 'checkout_click')
    by_day_scan = Counter(r['day'] for r in ev if r['name'] == 'food_scan')
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        daily.append({'day': d, 'pageviews': by_day_pv.get(d, 0),
                      'visitors': len(by_day_vis.get(d, ())),
                      'checkout_clicks': by_day_ck.get(d, 0),
                      'food_scans': by_day_scan.get(d, 0)})

    def counter_vis(rows_, keyf):
        c = Counter()
        vm = defaultdict(set)
        for r in rows_:
            k = keyf(r)
            if k is None or k == '':
                continue
            c[k] += 1
            if r['visitor_id']:
                vm[k].add(r['visitor_id'])
        return c, vm

    ok_pv = [r for r in pv if (r['status'] or 200) < 400]
    pages_c, pages_v = counter_vis(ok_pv, lambda r: r['path'])
    entries = [r for r in pv if r['new_session']]
    land_c, land_v = counter_vis(entries, lambda r: r['path'])
    src_c, src_v = counter_vis(entries, lambda r: r['source'] or 'direct')
    chan_c, chan_v = counter_vis(entries, lambda r: r['channel'] or 'direct')
    ext = [r for r in pv if r['ref_domain'] and r['channel'] not in ('internal',)]
    refd_c, refd_v = counter_vis(ext, lambda r: r['ref_domain'])
    reff_c, reff_v = counter_vis(ext, lambda r: (r['referrer'] or '')[:200])
    utm_rows = [r for r in pv if r['utm_source'] or r['utm_campaign'] or r['utm_medium']]
    utm_c, utm_v = counter_vis(utm_rows, lambda r: ' / '.join([
        r['utm_source'] or '-', r['utm_medium'] or '-', r['utm_campaign'] or '-']))

    visitor_first = {}
    for r in sorted(pv, key=lambda x: x['ts']):
        if r['visitor_id'] and r['visitor_id'] not in visitor_first:
            visitor_first[r['visitor_id']] = r

    def vis_counter(field):
        c = Counter()
        for r in visitor_first.values():
            c[r.get(field) or 'Unknown'] += 1
        return c

    # Country: prefer any row with a country for each visitor
    vis_country = {}
    for r in pv:
        if r['visitor_id'] and r['country'] and r['visitor_id'] not in vis_country:
            vis_country[r['visitor_id']] = r['country']
    country_c = Counter(vis_country.get(v, 'Unknown') for v in visitor_first)
    vis_tz = {}
    for r in pv:
        if r['visitor_id'] and r['tz'] and r['visitor_id'] not in vis_tz:
            vis_tz[r['visitor_id']] = r['tz']
    tz_c = Counter(vis_tz.get(v, 'Unknown') for v in visitor_first)

    nf_c, nf_v = counter_vis([r for r in pv if r['status'] == 404], lambda r: r['path'])

    eng = defaultdict(list)
    for r in ok_pv:
        if r['engaged_sec'] is not None and r['engaged_sec'] >= 0:
            eng[r['path']].append(r['engaged_sec'])
    engagement = sorted(
        [{'key': p, 'avg_engaged_sec': round(sum(v) / len(v), 1), 'samples': len(v)}
         for p, v in eng.items()],
        key=lambda x: -x['samples'])[:15]

    events_c, events_v = counter_vis(ev, lambda r: r['name'])
    scan_types = Counter()
    for r in ev:
        if r['name'] == 'food_scan':
            try:
                scan_types[(json.loads(r['meta'] or '{}') or {}).get('type') or 'unknown'] += 1
            except Exception:
                scan_types['unknown'] += 1

    # Funnel (distinct visitors in period, Root Cause pages)
    def vis_where(pred):
        return {r['visitor_id'] for r in prow if r['visitor_id'] and pred(r)}
    landed = vis_where(lambda r: r['kind'] == 'pageview')
    order_v = vis_where(lambda r: (r['kind'] == 'pageview' and r['path'] in ORDER_PATHS)
                        or (r['kind'] == 'event' and r['name'] == 'order_page_view'))
    ck_v = vis_where(lambda r: r['kind'] == 'event' and r['name'] == 'checkout_click')
    st_v = vis_where(lambda r: r['kind'] == 'event' and r['name'] == 'stripe_redirect')
    succ_v = vis_where(lambda r: (r['kind'] == 'event' and r['name'] == 'checkout_success'))
    scan_page_v = vis_where(lambda r: r['kind'] == 'pageview' and r['path'] in SCANNER_PATHS)
    scan_use_v = vis_where(lambda r: r['kind'] == 'event' and r['name'] == 'food_scan')

    def step(name, s, base):
        return {'step': name, 'visitors': len(s),
                'pct_of_landed': round(100.0 * len(s) / len(base), 1) if base else 0.0}
    funnel = [
        step('Landed (any page)', landed, landed),
        step('Viewed order page (/buy)', order_v, landed),
        step('Clicked checkout', ck_v, landed),
        step('Redirected to Stripe', st_v, landed),
        step('Reached checkout success', succ_v, landed),
    ]
    scanner_funnel = [
        step('Viewed Food Scanner', scan_page_v, landed),
        step('Used Food Scanner (any scan)', scan_use_v, landed),
        step('Scanner users who viewed /buy', scan_use_v & order_v, landed),
    ]

    bots = Counter()
    try:
        for b in store.bot_rows_since(d_period):
            bots[b['bot']] += b['hits'] or 0
    except Exception:
        pass

    recent = []
    for r in pv[:60]:
        ts = r['ts']
        try:
            local = ts.replace(tzinfo=timezone.utc).astimezone(CENTRAL) if CENTRAL else ts
            ts_s = local.strftime('%m/%d %I:%M %p')
        except Exception:
            ts_s = str(ts)
        recent.append({
            'time_ct': ts_s, 'path': r['path'], 'source': r['source'], 'device': r['device'],
            'browser': r['browser'], 'os': r['os'], 'country': r['country'] or '',
            'tz': r['tz'] or '', 'new_visitor': bool(r['new_visitor']),
            'visitor': (r['visitor_id'] or '')[:6], 'status': r['status'],
        })

    return {
        'generated_at_ct': now_c.strftime('%Y-%m-%d %I:%M %p %Z'),
        'site': site or 'all',
        'days': days,
        'include_internal': bool(include_internal),
        'summary': summary,
        'daily': daily,
        'top_pages': _top_with_visitors(pages_c, pages_v),
        'landing_pages': _top_with_visitors(land_c, land_v),
        'sources': _top_with_visitors(src_c, src_v, 20),
        'channels': _top_with_visitors(chan_c, chan_v),
        'referrer_domains': _top_with_visitors(refd_c, refd_v, 20),
        'referrers': _top_with_visitors(reff_c, reff_v, 20),
        'utm_campaigns': _top_with_visitors(utm_c, utm_v, 20),
        'devices': _top(vis_counter('device')),
        'browsers': _top(vis_counter('browser')),
        'os': _top(vis_counter('os')),
        'countries': _top(country_c, 20),
        'timezones': _top(tz_c, 15),
        'languages': _top(vis_counter('lang'), 15),
        'events': _top_with_visitors(events_c, events_v, 20),
        'food_scan_types': _top(scan_types),
        'funnel': funnel,
        'scanner_funnel': scanner_funnel,
        'not_found': _top_with_visitors(nf_c, nf_v, 10),
        'engagement': engagement,
        'bots': _top(bots, 20),
        'bot_hits_total': sum(bots.values()),
        'recent': recent,
    }


# ---------------------------------------------------------------------------
# Flask wiring
# ---------------------------------------------------------------------------

_BEACON_JS = (
    "<script>(function(){var id=window.__rcpv;if(!id||!navigator.sendBeacon)return;"
    "var vis=0,last=document.visibilityState==='visible'?Date.now():0,sent=0;"
    "function tz(){try{return Intl.DateTimeFormat().resolvedOptions().timeZone||''}catch(e){return''}}"
    "function send(x){var d={id:id,tz:tz(),sw:screen.width||0,sh:screen.height||0};"
    "for(var k in x)d[k]=x[k];try{navigator.sendBeacon('/api/analytics/beacon',"
    "new Blob([JSON.stringify(d)],{type:'text/plain'}))}catch(e){}}"
    "function acc(){if(last){vis+=Date.now()-last;last=0}}"
    "function bye(){acc();var t=Math.round(vis/1000);if(t>sent){sent=t;send({t:t})}}"
    "send({});"
    "document.addEventListener('visibilitychange',function(){"
    "if(document.visibilityState==='hidden'){bye()}else{last=Date.now()}});"
    "window.addEventListener('pagehide',bye);})();</script>"
)


def _default_db_url():
    url = (os.environ.get('ANALYTICS_DATABASE_URL') or '').strip()
    if url:
        return url, None
    try:
        from persistent_storage import setup_persistent_paths
        inst = setup_persistent_paths(_HERE)['instance_dir']
    except Exception:
        inst = os.path.join(_HERE, 'data', 'instance')
        os.makedirs(inst, exist_ok=True)
    return 'sqlite:///' + os.path.join(inst, 'analytics.db'), os.path.join(inst, 'analytics_salt.txt')


def _storage_info(store):
    info = {
        'backend': store.engine.dialect.name,
        'on_render': bool(os.environ.get('RENDER')),
        'data_dir_env_set': bool((os.environ.get('DATA_DIR') or '').strip()),
        'rows': None,
        'db_bytes': None,
        'queue_dropped': store.dropped,
        'write_errors': store.errors,
    }
    try:
        info['rows'] = store.total_rows()
    except Exception:
        pass
    try:
        if store.db_url.startswith('sqlite:///'):
            path = store.db_url[len('sqlite:///'):]
            info['db_bytes'] = os.path.getsize(path) if os.path.isfile(path) else 0
            data_dir = os.path.abspath(os.environ.get('DATA_DIR') or os.path.join(_HERE, 'data'))
            info['on_data_dir'] = os.path.abspath(path).startswith(data_dir)
    except Exception:
        pass
    info['persistent'] = (not info['on_render']) or (
        info['data_dir_env_set'] and info.get('on_data_dir', info['backend'] != 'sqlite'))
    return info


def register_visitor_analytics(app, get_current_user=None, db_url=None, salt_path=None,
                               disable_legacy=True):
    from flask import request, jsonify, render_template, redirect, make_response, g

    if db_url is None:
        db_url, default_salt = _default_db_url()
        salt_path = salt_path or default_salt
    store = AnalyticsStore(db_url, salt_path=salt_path)
    app.extensions['rc_visitor_analytics'] = store
    try:
        import atexit
        atexit.register(lambda: store.flush(3.0))
    except Exception:
        pass

    # Prune very old rows once per boot (default keep ~2 years).
    try:
        keep = int(os.environ.get('ANALYTICS_RETENTION_DAYS', '730'))
        store.submit(('prune', (central_now().date() - timedelta(days=keep)).isoformat()))
    except Exception:
        pass

    # Retire the legacy before_request logger (stored raw IPs on every request,
    # including static files and bots). Old PageView rows are left untouched.
    if disable_legacy and os.environ.get('LEGACY_PAGEVIEW_LOG') != '1':
        try:
            funcs = app.before_request_funcs.get(None, [])
            app.before_request_funcs[None] = [
                f for f in funcs if getattr(f, '__name__', '') != 'before_request_analytics'
            ]
        except Exception:
            pass

    def _is_admin():
        try:
            user = get_current_user() if get_current_user else None
            return bool(user and getattr(user, 'is_admin', False))
        except Exception:
            return False

    def _token_ok():
        token = (os.environ.get('ANALYTICS_API_TOKEN') or '').strip()
        if not token or len(token) < 16:
            return False
        supplied = (request.headers.get('Authorization') or '').strip()
        if supplied.lower().startswith('bearer '):
            supplied = supplied[7:].strip()
        else:
            supplied = (request.headers.get('X-Analytics-Token') or request.args.get('token') or '').strip()
        return bool(supplied) and hmac.compare_digest(supplied.encode(), token.encode())

    def _session_is_admin():
        try:
            from flask import session
            return bool(session.get('is_admin'))
        except Exception:
            return False

    def _track_kind():
        """Return 'page', 'event:<name>', or None."""
        path = request.path or '/'
        method = request.method
        if method == 'GET':
            if path in SKIP_EXACT or any(path.startswith(p) for p in SKIP_PREFIXES):
                m = FOOD_SCAN_API.match(path)
                if m:
                    return 'event:food_scan'
                return None
            purpose = (request.headers.get('Purpose') or request.headers.get('Sec-Purpose')
                       or request.headers.get('X-Moz') or '').lower()
            if 'prefetch' in purpose or 'prerender' in purpose:
                return None
            return 'page'
        if method == 'POST':
            if path == '/create-checkout-session':
                return 'event:checkout_click'
            if FOOD_SCAN_API.match(path):
                return 'event:food_scan'
            if path == '/contact':
                return 'event:contact_submit'
            if path == '/register':
                return 'event:signup_submit'
        return None

    def _ids():
        vid = request.cookies.get(VISITOR_COOKIE) or ''
        new_visitor = not _UUID_RE.match(vid)
        if new_visitor:
            vid = uuid.uuid4().hex
        sid = request.cookies.get(SESSION_COOKIE) or ''
        new_session = not _UUID_RE.match(sid)
        if new_session:
            sid = uuid.uuid4().hex
        return vid, sid, new_visitor, new_session

    def _base_row(kind, name, status, vid, sid, new_visitor, new_session, day):
        ua = request.headers.get('User-Agent') or ''
        device, browser, os_name = parse_ua(ua)
        ref = (request.headers.get('Referer') or '')[:500]
        rdom = referrer_domain(ref)
        args = request.args
        utm_source = (args.get('utm_source') or '')[:100]
        source, channel = classify_source(rdom, utm_source, request.host)
        if not utm_source and (args.get('gclid') or args.get('gbraid') or args.get('wbraid')):
            source, channel = 'google', 'paid'
        elif not utm_source and args.get('fbclid') and channel in ('direct', 'internal'):
            source, channel = 'facebook', 'social'
        elif not utm_source and args.get('twclid') and channel in ('direct', 'internal'):
            source, channel = 'x', 'social'
        country = _header_country(request.headers)
        path = request.path or '/'
        internal = bool(_session_is_admin() or request.cookies.get(INTERNAL_COOKIE) == '1')
        return {
            'eid': uuid.uuid4().hex[:24],
            'ts': datetime.now(timezone.utc).replace(tzinfo=None),
            'day': day,
            'kind': kind,
            'name': name,
            'site': site_section(path),
            'path': path[:300],
            'status': status,
            'referrer': ref,
            'ref_domain': rdom[:120],
            'source': source,
            'channel': channel,
            'utm_source': utm_source,
            'utm_medium': (args.get('utm_medium') or '')[:100],
            'utm_campaign': (args.get('utm_campaign') or '')[:150],
            'utm_term': (args.get('utm_term') or '')[:150],
            'utm_content': (args.get('utm_content') or '')[:150],
            'country': country,
            'country_src': 'header' if country else '',
            'lang': _short_lang(request.headers.get('Accept-Language')),
            'device': device,
            'browser': browser,
            'os': os_name,
            'visitor_id': vid,
            'session_id': sid,
            'new_visitor': new_visitor,
            'new_session': new_session,
            'ip_hash': store.ip_hash(_client_ip(request), day),
            'logged_in': bool(_safe_session_get('user_id')),
            'internal': internal,
            'tz': None,
            'screen': None,
            'engaged_sec': None,
            'js': False,
            'meta': None,
        }

    def _safe_session_get(key):
        try:
            from flask import session
            return session.get(key)
        except Exception:
            return None

    def _set_cookies(response, vid, sid):
        secure = bool(request.is_secure)
        response.set_cookie(VISITOR_COOKIE, vid, max_age=VISITOR_MAX_AGE, httponly=True,
                            samesite='Lax', secure=secure, path='/')
        response.set_cookie(SESSION_COOKIE, sid, max_age=SESSION_MAX_AGE, httponly=True,
                            samesite='Lax', secure=secure, path='/')

    @app.after_request
    def _rc_visitor_track(response):
        try:
            kind = _track_kind()
            if not kind:
                return response
            ua = request.headers.get('User-Agent') or ''
            day = central_now().date().isoformat()
            if kind == 'page':
                ctype = response.headers.get('Content-Type') or ''
                if 'text/html' not in ctype or response.status_code not in (200, 404):
                    return response
                if is_bot(ua):
                    store.submit(('bot', day, bot_name(ua)[:40]))
                    return response
            elif is_bot(ua):
                return response

            vid, sid, new_visitor, new_session = _ids()
            if kind == 'page':
                row = _base_row('pageview', 'pageview', response.status_code, vid, sid,
                                new_visitor, new_session, day)
                store.submit(('insert', row))
                path = request.path or '/'
                extra = []
                if response.status_code == 200 and path in ORDER_PATHS:
                    extra.append(('order_page_view', None))
                if response.status_code == 200 and path == '/checkout/success':
                    extra.append(('checkout_success', {'has_session': bool(request.args.get('session_id'))}))
                for name, meta in extra:
                    er = dict(row, eid=uuid.uuid4().hex[:24], kind='event', name=name,
                              new_visitor=False, new_session=False,
                              meta=json.dumps(meta) if meta else None)
                    store.submit(('insert', er))
                # Inject beacon (first-party) for engaged time / timezone / screen.
                if (response.status_code == 200 and not response.direct_passthrough
                        and os.environ.get('ANALYTICS_BEACON', '1') != '0'):
                    html = response.get_data(as_text=True)
                    if '</body>' in html and '__rcpv' not in html:
                        snippet = '<script>window.__rcpv="%s";</script>%s' % (row['eid'], _BEACON_JS)
                        idx = html.rfind('</body>')
                        response.set_data(html[:idx] + snippet + html[idx:])
            else:
                name = kind.split(':', 1)[1]
                meta = {}
                status = response.status_code
                path = request.path or '/'
                if name == 'food_scan':
                    m = FOOD_SCAN_API.match(path)
                    meta = {'type': m.group(1) if m else 'unknown', 'ok': status < 400}
                elif name == 'checkout_click':
                    meta = {'product': (request.form.get('product') or request.args.get('product') or 'single')[:20]}
                elif name in ('contact_submit', 'signup_submit'):
                    meta = {'ok': status in (200, 302, 303)}
                row = _base_row('event', name, status, vid, sid, new_visitor, new_session, day)
                row['meta'] = json.dumps(meta) if meta else None
                store.submit(('insert', row))
                if name == 'checkout_click':
                    loc = response.headers.get('Location') or ''
                    if status in (301, 302, 303, 307) and 'stripe.com' in loc:
                        store.submit(('insert', dict(row, eid=uuid.uuid4().hex[:24], name='stripe_redirect',
                                                     new_visitor=False, new_session=False)))
                    elif status >= 300:
                        store.submit(('insert', dict(row, eid=uuid.uuid4().hex[:24], name='checkout_error',
                                                     new_visitor=False, new_session=False)))
            _set_cookies(response, vid, sid)
        except Exception as exc:
            try:
                store.errors += 1
                store.last_error = 'track: %s' % str(exc)[:200]
            except Exception:
                pass
        return response

    def beacon():
        try:
            raw = request.get_data(cache=False, as_text=True) or ''
            if len(raw) > 2000:
                return ('', 204)
            data = json.loads(raw or '{}')
            eid = str(data.get('id') or '')
            if not _ID_RE.match(eid):
                return ('', 204)
            values = {'js': True}
            tz = str(data.get('tz') or '')[:64]
            if tz and re.match(r'^[A-Za-z_]+(/[A-Za-z0-9_\-+]+){0,2}$', tz):
                values['tz'] = tz
                cc = _load_tz_country().get(tz)
                if cc:
                    values['tz_country'] = cc
            try:
                sw, sh = int(data.get('sw') or 0), int(data.get('sh') or 0)
                if 0 < sw < 20000 and 0 < sh < 20000:
                    values['screen'] = '%dx%d' % (sw, sh)
            except Exception:
                pass
            tz_country = values.pop('tz_country', None)
            store.submit(('update', eid, values))
            if tz_country:
                store.submit(('tzcountry', eid, tz_country))
            if 't' in data:
                try:
                    secs = max(0, min(int(data.get('t') or 0), 4 * 3600))
                    store.submit(('engaged', eid, secs))
                except Exception:
                    pass
        except Exception:
            pass
        return ('', 204)

    def self_check():
        """Lets any visitor confirm what's recorded for *their own* anonymous cookie."""
        vid = request.cookies.get(VISITOR_COOKIE) or ''
        if not _UUID_RE.match(vid):
            return jsonify({'tracking': True, 'visitor_cookie': False, 'pageviews': 0, 'events': 0})
        store.flush(2.0)
        try:
            n, ev, last = store.visitor_summary(vid)
        except Exception:
            return jsonify({'tracking': True, 'visitor_cookie': True, 'error': 'unavailable'}), 503
        out = {'tracking': True, 'visitor_cookie': True, 'pageviews': n, 'events': ev}
        if last is not None:
            out['last_path'] = last[1]
            out['excluded_as_internal'] = bool(last[2])
        resp = jsonify(out)
        resp.headers['Cache-Control'] = 'no-store'
        return resp

    def _params():
        try:
            days = int(request.args.get('days') or 30)
        except Exception:
            days = 30
        site = (request.args.get('site') or 'rootcause').strip().lower()
        if site not in ('rootcause', 'apexforge', 'foam', 'all'):
            site = 'rootcause'
        include_internal = request.args.get('include_internal') in ('1', 'true', 'yes')
        return days, site, include_internal

    def stats_json():
        if not (_is_admin() or _token_ok()):
            resp = jsonify({'error': 'unauthorized',
                            'hint': 'Log in as admin, or send Authorization: Bearer <ANALYTICS_API_TOKEN>.'})
            resp.headers['Cache-Control'] = 'no-store'
            return resp, 401
        store.flush(2.0)
        days, site, include_internal = _params()
        data = build_stats(store, days=days, site=site, include_internal=include_internal)
        data['storage'] = _storage_info(store)
        data['third_party_tags'] = {k: bool(v) for k, v in _tag_config().items()}
        resp = jsonify(data)
        resp.headers['Cache-Control'] = 'no-store'
        return resp

    def stats_page():
        if not (_is_admin() or (_token_ok() and request.headers.get('Authorization'))):
            from flask import flash
            try:
                flash('Admin access required.', 'error')
            except Exception:
                pass
            return redirect('/login')
        if request.args.get('ignore_me') in ('1', '0'):
            resp = make_response(redirect('/admin/stats'))
            if request.args.get('ignore_me') == '1':
                resp.set_cookie(INTERNAL_COOKIE, '1', max_age=5 * VISITOR_MAX_AGE, httponly=True,
                                samesite='Lax', secure=bool(request.is_secure), path='/')
            else:
                resp.delete_cookie(INTERNAL_COOKIE, path='/')
            return resp
        store.flush(2.0)
        days, site, include_internal = _params()
        data = build_stats(store, days=days, site=site, include_internal=include_internal)
        data['storage'] = _storage_info(store)
        maxv = max([d['pageviews'] for d in data['daily']] + [1])
        chart = []
        n = len(data['daily'])
        width = 760
        bw = max(2.0, width / max(n, 1))
        for i, d in enumerate(data['daily']):
            h_pv = 150.0 * d['pageviews'] / maxv
            h_v = 150.0 * d['visitors'] / maxv
            chart.append({'x': round(i * bw, 2), 'w': round(max(bw - 2, 1), 2),
                          'h_pv': round(h_pv, 2), 'h_v': round(h_v, 2),
                          'day': d['day'], 'pv': d['pageviews'], 'v': d['visitors']})
        resp = make_response(render_template(
            'admin_stats.html', stats=data, chart=chart, chart_max=maxv,
            tags={k: bool(v) for k, v in _tag_config().items()},
            ignoring=request.cookies.get(INTERNAL_COOKIE) == '1',
            token_configured=bool((os.environ.get('ANALYTICS_API_TOKEN') or '').strip()),
        ))
        resp.headers['Cache-Control'] = 'no-store'
        return resp

    for path, endpoint, view, methods in (
        ('/api/analytics/beacon', 'rc_analytics_beacon', beacon, ['POST']),
        ('/api/analytics/self', 'rc_analytics_self', self_check, ['GET']),
        ('/admin/stats', 'rc_admin_stats', stats_page, ['GET']),
        ('/admin/stats.json', 'rc_admin_stats_json', stats_json, ['GET']),
    ):
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = view
        else:
            app.add_url_rule(path, endpoint, view, methods=methods)

    # ----- Third-party tags (template context) -----------------------------
    def _tag_config():
        ga = _tag_value('GA_MEASUREMENT_ID').upper()
        clarity = _tag_value('CLARITY_PROJECT_ID').lower()
        gsc = _tag_value('GOOGLE_SITE_VERIFICATION')
        bing = _tag_value('BING_SITE_VERIFICATION')
        return {
            'ga_id': ga if _GA_RE.match(ga) else '',
            'clarity_id': clarity if _CLARITY_RE.match(clarity) else '',
            'gsc': gsc if _VERIFY_RE.match(gsc) else '',
            'bing': bing if _VERIFY_RE.match(bing) else '',
        }

    @app.context_processor
    def _rc_tags_ctx():
        try:
            cfg = _tag_config()
            path = request.path or '/'
            private = any(path == p or path.startswith(p + '/') for p in PRIVATE_PREFIXES)
            gpc = (request.headers.get('Sec-GPC') or '').strip() == '1'
            internal = request.cookies.get(INTERNAL_COOKIE) == '1' or _session_is_admin()
            cfg['load_trackers'] = not (private or gpc or internal)
            return {'rc_tags': cfg}
        except Exception:
            return {'rc_tags': {}}

    print('[Root Cause] Visitor analytics registered (%s)' % store.engine.dialect.name)
    return store
