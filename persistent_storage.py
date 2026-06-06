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


def _migrate_legacy_data(basedir, data_dir):
    """Copy old instance/ and uploads/ into the persistent data folder once."""
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
    }