"""Cross-platform inter-process lock (no fcntl/msvcrt): atomic create-exclusive lock file with stale-lock recovery."""
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(name: str = "crimemind_initdb_excl", timeout: float = 600, stale_after: float = 900):
    path = Path(tempfile.gettempdir()) / f"{name}.lock"
    start = time.time()
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > stale_after:
                    path.unlink()
                    continue
            except OSError:
                pass
            if time.time() - start > timeout:
                raise TimeoutError(f"could not acquire lock {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass
