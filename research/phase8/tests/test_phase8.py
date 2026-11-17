"""Phase 8 tests: aggregation, figures, runner planning, manifest integrity. They read stored results; they do not rerun experiments."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from research.phase8 import aggregate, plots

ROOT = Path(__file__).resolve().parents[3]


def test_results_index_hashes_match_files(tmp_path):
    rows = aggregate.write_index(tmp_path)
    assert rows and (tmp_path / "results_index.csv").exists() and (tmp_path / "results_index.md").exists()
    for r in rows[:25]:
        assert hashlib.sha256((ROOT / r["file"]).read_bytes()).hexdigest() == r["sha256"]
    assert {r["phase"] for r in rows} == {"phase3", "phase4", "phase5", "phase6", "phase7"}


def test_headline_ranking_has_expected_methods_and_bounds():
    hr = aggregate.headline_ranking()
    assert {"random", "q40", "q40_r", "raeer", "spatial_proximity"} <= set(hr)
    for m in hr.values():
        for k in ("nDCG@5", "MRR"):
            if k in m:
                assert 0 <= m[k]["lo"] <= m[k]["mean"] <= m[k]["hi"] <= 1


def test_figures_are_built_from_results_with_captions_and_sources(tmp_path):
    figs = plots.build(tmp_path)
    assert len(figs) == 9
    for f in figs:
        assert (tmp_path / f["file"]).stat().st_size > 5000 and f["caption"] and f["source"]
    assert "LLM" in (tmp_path / "figure_index.md").read_text() or "template" in (tmp_path / "figure_index.md").read_text()


def test_run_all_dry_run_lists_every_phase_without_executing():
    out = subprocess.run([sys.executable, "-m", "research.run_all", "--dry-run", "--phases", "3", "4", "5", "6", "7"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0
    for ph in "34567":
        assert f"phase {ph} [experiment]" in out.stdout


def test_run_all_manifest_records_all_datasets_and_frozen_bundle():
    runs = sorted((ROOT / "research/phase8/results").glob("P8-*/run_all_manifest.json"))
    runs = [r for r in runs if not json.load(open(r))["quick"]]
    if not runs:
        pytest.skip("no full run_all manifest yet")
    m = json.load(open(runs[-1]))
    assert len(m["datasets"]) == 50 and m["frozen_q40_bundle"] and m["configs"] and m["git_commit"]


def test_headline_numbers_in_final_report_come_from_results():
    txt = (ROOT / "research/FINAL_RESEARCH_REPORT.md").read_text(encoding="utf-8")
    hr = aggregate.headline_ranking()
    assert f"{hr['raeer']['nDCG@5']['mean']:.3f}" in txt and f"{hr['q40']['nDCG@5']['mean']:.3f}" in txt
    assert "NOT RUN" in txt and "requires literature verification" in txt.lower()
