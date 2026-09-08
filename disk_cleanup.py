"""Free disk so admin scan uploads can finish (Errno 28)."""
import os
import time
import tempfile


def _dir_size(path):
    total = 0
    if not os.path.isdir(path):
        return 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _free_bytes(path):
    try:
        usage = os.statvfs(path)
        return usage.f_bavail * usage.f_frsize
    except OSError:
        return 0


def _delete(path):
    try:
        size = os.path.getsize(path)
        os.remove(path)
        return size
    except OSError:
        return 0


def _purge_old(folder, max_age_sec, patterns=None):
    freed = 0
    if not os.path.isdir(folder):
        return 0
    cutoff = time.time() - max_age_sec
    for root, _dirs, files in os.walk(folder):
        for name in files:
            lower = name.lower()
            if patterns and not any(lower.endswith(p) or p in lower for p in patterns):
                continue
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) <= cutoff:
                    freed += _delete(path)
            except OSError:
                continue
    return freed


def _purge_largest(folder, keep_bytes, min_file_bytes=0):
    if not os.path.isdir(folder):
        return 0
    files = []
    for root, _dirs, names in os.walk(folder):
        for name in names:
            path = os.path.join(root, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size >= min_file_bytes:
                files.append((size, path))
    files.sort(reverse=True)
    freed = 0
    current = _dir_size(folder)
    for size, path in files:
        if current <= keep_bytes:
            break
        gone = _delete(path)
        freed += gone
        current -= gone
    return freed


def free_disk(storage=None, target_free_mb=250):
    target = target_free_mb * 1024 * 1024
    probe = storage.get('data_dir') if storage else '/tmp'
    before = _free_bytes(probe or '/tmp')
    freed = 0
    for folder in ('/tmp', tempfile.gettempdir()):
        freed += _purge_old(
            folder,
            max_age_sec=20 * 60,
            patterns=('.pdf', '.xml', '.zip', '.bin', 'tmp', 'werkzeug'),
        )
    if storage:
        freed += _purge_largest(storage.get('scan_pdfs_dir'), keep_bytes=80 * 1024 * 1024, min_file_bytes=1500000)
        freed += _purge_largest(storage.get('reports_dir'), keep_bytes=120 * 1024 * 1024, min_file_bytes=2000000)
    after = _free_bytes(probe or '/tmp')
    print(
        f'[Root Cause] Disk cleanup freed {freed / (1024 * 1024):.1f} MB. '
        f'Free now {after / (1024 * 1024):.1f} MB (was {before / (1024 * 1024):.1f} MB).'
    )
    return {
        'freed_bytes': freed,
        'free_before': before,
        'free_after': after,
        'enough': after >= target or after > before,
    }
