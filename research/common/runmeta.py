"""Reproducibility metadata for every experiment run (unique run id, git commit, versions, hardware)."""
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def git_dirty() -> bool:
    try:
        return bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        return True


def new_run_id(prefix: str) -> str:
    return f"{prefix}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}-{git_commit()}"


def environment(pg_version: str | None = None) -> dict:
    pk = {}
    for n in ("numpy", "scipy", "matplotlib", "psycopg", "fastapi", "pytest", "networkx"):
        try:
            pk[n] = metadata.version(n)
        except metadata.PackageNotFoundError:
            pk[n] = None
    return {"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "git_commit": git_commit(), "git_dirty": git_dirty(),
            "python": sys.version.split()[0], "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "postgres": pg_version, "packages": pk}


def write_manifest(outdir: Path, run_id: str, **fields) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    m = {"run_id": run_id, "environment": environment(fields.pop("pg_version", None)), **fields}
    (outdir / "run_manifest.json").write_text(json.dumps(m, indent=1, sort_keys=True, default=str))
    return m
