"""Disposable per-seed research database: regenerate a Phase 2 dataset from its seed, verify it against the committed
manifest hash, expose a connection, drop it on exit. Never touches the application database."""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from research.common.portable_lock import file_lock   # noqa: E402
from research.generate_datasets import TABLES, export_table   # noqa: E402
from synth.research_seed import BASE, seed_database   # noqa: E402

R = ROOT / "research"


def load_ground_truth(seed: int) -> dict:
    """Evaluator-only. Algorithms never receive this."""
    return json.load(open(R / "ground_truth" / f"seed_{seed}.json"))["cases"]


class SeedWorkspace:
    def __init__(self, seed: int, prefix: str = "cm_rw", verify: bool = True, keep: bool = False):
        self.seed, self.verify, self.keep = seed, verify, keep
        self.db = f"{prefix}_{seed}"
        self.conn = None
        self.hash_verified = None

    def __enter__(self):
        with file_lock():
            subprocess.run([sys.executable, str(ROOT / "scripts" / "init_db.py"), "--db", self.db, "--reset"], check=True,
                           capture_output=True, cwd=ROOT / "backend")
        cfg = json.load(open(R / "generation_config.json"))
        seed_database(self.db, self.seed, cfg)
        self.conn = psycopg.connect(f"{BASE}/{self.db}", row_factory=dict_row)
        self.conn.execute("SELECT set_config('app.user','system.research',false)")
        if self.verify:
            want = json.load(open(R / "datasets" / f"seed_{self.seed}" / "dataset_manifest.json"))["summary"]["content_sha256"]
            with tempfile.TemporaryDirectory() as td:
                tabs = {n: export_table(self.conn, n, q, Path(td)) for n, q in TABLES.items()}
            got = hashlib.sha256("".join(tabs[k]["sha256"] for k in sorted(tabs)).encode()).hexdigest()
            self.hash_verified = got == want
            if not self.hash_verified:
                self.__exit__(None, None, None)
                raise RuntimeError(f"seed {self.seed}: regenerated dataset hash differs from committed manifest")
        return self

    def cases(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT case_id, case_ref FROM cases ORDER BY case_ref")]

    def pg_version(self) -> str:
        return self.conn.execute("SHOW server_version").fetchone()["server_version"]

    def __exit__(self, *exc):
        try:
            if self.conn:
                self.conn.close()
        finally:
            if not self.keep:
                with psycopg.connect(f"{BASE}/postgres", autocommit=True) as c:
                    c.execute(f'DROP DATABASE IF EXISTS "{self.db}" WITH (FORCE)')
        return False
