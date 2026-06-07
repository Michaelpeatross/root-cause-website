"""Persistent data paths for SQLite and uploaded files (survives Render redeploys)."""
import os
import shutil


def _tree_has_files(path):
    if not os.path.isdir(path):
        return False
    for _root, _dirs, files in os.walk(path):
        if files:
            return True
    return False


def _db_stats(db_path):
    if not os.path.isfile(db_path):
        return {'exists': False, 'bytes': 0, 'user_count': 0, 'report_count': 0}
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            users = (
                conn.execute('SELECT COUNT(*) FROM user').fetchone()[0]
                if 'user' in tables else 0
            )
            reports = (
                conn.execute('SELECT COUNT(*) FROM report').fetchone()[0]
                if 'report' in tables else 0
            )
        finally:
            conn.close()
        return {
            'exists': True,
            'bytes': os.path.getsize(db_path),
            'user_count': users,
            'report_count': reports,
        }
    except Exception:
        return {
            'exists': True,
            'bytes': os.path.getsize(db_path),
            'user_count': -1,
            'report_count': -1,
        }


def _migrate_legacy_data(basedir, data_dir):
    """
    Copy old local instance/ and uploads/ into the persistent data folder once.

    On Render we never seed from the repo's instance/ folder — that file is often
    an outdated copy committed to git and would wipe live client accounts on redeploy.
    """
    if os.environ.get('RENDER'):
        return

    legacy_db = os.path.join(basedir, 'instance', 'rootcause.db')
    new_db = os.path.join(data_dir, 'instance', 'rootcause.db')
    if os.path.isfile(legacy_db) and not os.path.isfile(new_db):
        os.makedirs(os.path.dirname(new_db), exist_ok=True)
        shutil.copy2(legacy_db, new_db)

    legacy_uploads = os.path.join(basedir, 'uploads')
    new_uploads = os.path.join(data_dir, 'uploads')
    if _tree_has_files(legacy_uploads) and not _tree_has_files(new_uploads):
        shutil.copytree(legacy_uploads, new_uploads, dirs_exist_ok=True)


def setup_persistent_paths(basedir):
    """
    All client accounts, passwords (hashed), and uploads live under data_dir.
    On Render, mount a persistent disk at this path so redeploys keep data.
    """
    data_dir = os.environ.get('DATA_DIR', os.path.join(basedir, 'data'))
    data_dir = os.path.abspath(data_dir)

    instance_dir = os.path.join(data_dir, 'instance')
    uploads_dir = os.path.join(data_dir, 'uploads')
    reports_dir = os.path.join(uploads_dir, 'reports')
    documents_dir = os.path.join(uploads_dir, 'documents')
    scan_pdfs_dir = os.path.join(uploads_dir, 'scan_pdfs')

    for folder in (instance_dir, reports_dir, documents_dir, scan_pdfs_dir):
        os.makedirs(folder, exist_ok=True)

    _migrate_legacy_data(basedir, data_dir)

    db_path = os.path.join(instance_dir, 'rootcause.db')
    return {
        'data_dir': data_dir,
        'instance_dir': instance_dir,
        'uploads_dir': uploads_dir,
        'reports_dir': reports_dir,
        'documents_dir': documents_dir,
        'scan_pdfs_dir': scan_pdfs_dir,
        'database_uri': f'sqlite:///{db_path}',
        'db_path': db_path,
    }


def get_storage_status(storage):
    """Diagnostics for admin UI and startup logs."""
    on_render = bool(os.environ.get('RENDER'))
    data_dir_env = (os.environ.get('DATA_DIR') or '').strip()
    db_path = storage['db_path']
    stats = _db_stats(db_path)
    basedir = os.path.abspath(os.path.dirname(__file__))
    legacy_db = os.path.join(basedir, 'instance', 'rootcause.db')

    warnings = []
    if on_render and not data_dir_env:
        warnings.append(
            'DATA_DIR is not set on Render. Add env var DATA_DIR=/opt/render/project/src/data '
            'and attach a persistent disk at that path, or client data will reset on every deploy.'
        )
    if on_render and os.path.isfile(legacy_db):
        warnings.append(
            'Repo contains instance/rootcause.db — it is ignored on Render but should be '
            'removed from git so local deploys do not accidentally restore stale data.'
        )
    if on_render and stats['exists'] and stats['bytes'] < 2048 and stats['user_count'] <= 1:
        warnings.append(
            'Database looks empty or freshly created. Confirm the Render persistent disk '
            '(rootcause-data) is mounted at /opt/render/project/src/data.'
        )

    return {
        'on_render': on_render,
        'data_dir': storage['data_dir'],
        'db_path': db_path,
        'data_dir_env_set': bool(data_dir_env),
        'data_dir_env': data_dir_env or '(default: ./data)',
        'persistent': not on_render or bool(data_dir_env),
        'warnings': warnings,
        **stats,
    }