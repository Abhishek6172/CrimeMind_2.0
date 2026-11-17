"""Experiment Runner: executes genuine algorithm inferences and records metrics."""
import json
import logging
import time
import traceback
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from .. import config
from .dataset_service import dataset_service
from .experiment_config import config_manager
from .metrics_service import metrics_service

log = logging.getLogger("crimemind.research")


class ExperimentRunner:
    """Executes single research experiments synchronously within worker threads."""

    def __init__(self):
        self._cancel_flags: Dict[int, bool] = {}

    def request_cancel(self, experiment_id: int) -> None:
        self._cancel_flags[experiment_id] = True

    def run_experiment_sync(
        self,
        experiment_id: int,
        algorithm_name: str,
        dataset_id: str,
        seeds: List[int],
        cases_filter: Optional[List[str]],
        parameters: Optional[Dict[str, Any]],
        target_metrics: List[str],
        perturbation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Executes the research experiment, updates progress and writes results to PostgreSQL."""
        start_time = time.time()
        self._cancel_flags[experiment_id] = False

        self._set_status(experiment_id, "RUNNING", progress_pct=5.0, current_step="Initializing algorithm & dataset")
        self._log(experiment_id, "INFO", f"Starting experiment #{experiment_id} ({algorithm_name}) across {len(seeds)} seeds...")

        try:
            # 1. Instantiate genuine algorithm
            algo, merged_cfg = config_manager.instantiate_algorithm(algorithm_name, parameters)
            self._log(experiment_id, "INFO", f"Algorithm instantiated: {algo.name} (config version: {algo.config_version})")

            # 2. Iterate through seeds and cases
            total_seeds = len(seeds)
            seed_case_results = []
            
            for s_idx, seed in enumerate(seeds):
                if self._cancel_flags.get(experiment_id, False):
                    self._set_status(experiment_id, "CANCELLED", current_step="Experiment cancelled by user")
                    self._log(experiment_id, "WARNING", f"Experiment #{experiment_id} was cancelled by user.")
                    return

                pct = 10.0 + (s_idx / total_seeds) * 80.0
                step_desc = f"Evaluating seed {seed} ({s_idx + 1}/{total_seeds})"
                self._set_status(experiment_id, "RUNNING", progress_pct=round(pct, 1), current_step=step_desc)
                self._log(experiment_id, "INFO", f"Loading dataset for seed {seed}...")

                # Load views and ground truth
                case_views = dataset_service.load_seed_cases(seed, cases_filter, perturbation)
                gt_cases = dataset_service.get_ground_truth(seed)

                for case_ref, view in sorted(case_views.items()):
                    if self._cancel_flags.get(experiment_id, False):
                        self._set_status(experiment_id, "CANCELLED", current_step="Experiment cancelled by user")
                        return

                    if case_ref not in gt_cases:
                        self._log(experiment_id, "WARNING", f"No ground truth found for case {case_ref} in seed {seed}, skipping.")
                        continue

                    gt = gt_cases[case_ref]
                    grades = gt.get("relevance_grades", {})

                    # Run genuine algorithm ranking
                    ranked_results = algo.rank(f"seed_{seed}", view, merged_cfg)
                    sorted_ranks = sorted(ranked_results, key=lambda r: r.rank)
                    ranked_lead_ids = [r.lead_id for r in sorted_ranks]

                    # Exact metrics calculation
                    case_metrics = metrics_service.evaluate(ranked_lead_ids, grades)

                    # Top 10 ranked candidates with details
                    top_candidates = [
                        {
                            "rank": r.rank,
                            "lead_id": r.lead_id,
                            "raw_score": round(r.raw_score, 4),
                            "explanation": r.explanation,
                            "is_relevant": bool(grades.get(r.lead_id, 0) >= 1),
                            "relevance_grade": grades.get(r.lead_id, 0),
                        }
                        for r in sorted_ranks[:10]
                    ]

                    # Record seed result
                    seed_res = {
                        "seed": seed,
                        "case_ref": case_ref,
                        "metrics": case_metrics,
                        "top_ranked": top_candidates,
                        "n_candidates": len(view.candidates),
                        "n_relevant": sum(1 for v in grades.values() if v >= 1),
                    }
                    seed_case_results.append(seed_res)

                    self._log(
                        experiment_id,
                        "INFO",
                        f"Seed {seed} | {case_ref} evaluated: nDCG@5={case_metrics.get('nDCG@5', 0):.4f}, "
                        f"P@5={case_metrics.get('P@5', 0):.4f}, MRR={case_metrics.get('MRR', 0):.4f}"
                    )

            # 3. Aggregate metrics across all seeds and cases
            self._set_status(experiment_id, "RUNNING", progress_pct=92.0, current_step="Aggregating multi-seed statistics")
            metric_summaries = metrics_service.aggregate_metrics(seed_case_results, target_metrics)

            # 4. Save results to PostgreSQL in a transaction
            elapsed_sec = round(time.time() - start_time, 3)
            with psycopg.connect(config.DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    # Insert metrics
                    for m in metric_summaries:
                        cur.execute(
                            """
                            INSERT INTO research_experiment_metrics (
                                experiment_id, metric_name, mean_value, std_dev, std_err,
                                ci_lower, ci_upper, min_value, max_value
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                experiment_id,
                                m["metric_name"],
                                m["mean_value"],
                                m["std_dev"],
                                m["std_err"],
                                m["ci_lower"],
                                m["ci_upper"],
                                m["min_value"],
                                m["max_value"],
                            ),
                        )

                    # Insert seed case results
                    for sr in seed_case_results:
                        cur.execute(
                            """
                            INSERT INTO research_experiment_seed_results (
                                experiment_id, seed, case_ref, metrics_json, top_ranked, n_candidates, n_relevant
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                experiment_id,
                                sr["seed"],
                                sr["case_ref"],
                                json.dumps(sr["metrics"]),
                                json.dumps(sr["top_ranked"]),
                                sr["n_candidates"],
                                sr["n_relevant"],
                            ),
                        )

                    # Mark COMPLETED
                    cur.execute(
                        """
                        UPDATE research_experiments
                        SET status = 'COMPLETED', progress_pct = 100.00,
                            current_step = 'Completed successfully', execution_time_sec = %s,
                            completed_at = now()
                        WHERE experiment_id = %s
                        """,
                        (elapsed_sec, experiment_id),
                    )
                conn.commit()

            self._log(
                experiment_id,
                "INFO",
                f"Experiment #{experiment_id} successfully COMPLETED in {elapsed_sec:.2f}s across {len(seed_case_results)} case evaluations."
            )

        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}"
            tb = traceback.format_exc()
            log.exception(f"Experiment #{experiment_id} failed: {e}")
            self._set_status(experiment_id, "FAILED", error_message=err_msg, current_step="Execution failed")
            self._log(experiment_id, "ERROR", f"Execution error: {err_msg}\n{tb}")

    def _set_status(
        self,
        experiment_id: int,
        status: str,
        progress_pct: Optional[float] = None,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        try:
            with psycopg.connect(config.DATABASE_URL) as conn:
                updates = ["status = %s"]
                vals = [status]
                if progress_pct is not None:
                    updates.append("progress_pct = %s")
                    vals.append(progress_pct)
                if current_step is not None:
                    updates.append("current_step = %s")
                    vals.append(current_step)
                if error_message is not None:
                    updates.append("error_message = %s")
                    vals.append(error_message)
                if status == "RUNNING":
                    updates.append("started_at = coalesce(started_at, now())")

                vals.append(experiment_id)
                query = f"UPDATE research_experiments SET {', '.join(updates)} WHERE experiment_id = %s"
                conn.execute(query, tuple(vals))
                conn.commit()
        except Exception:
            pass

    def _log(self, experiment_id: int, level: str, message: str) -> None:
        try:
            with psycopg.connect(config.DATABASE_URL) as conn:
                conn.execute(
                    "INSERT INTO research_experiment_logs (experiment_id, level, message) VALUES (%s, %s, %s)",
                    (experiment_id, level, message),
                )
                conn.commit()
        except Exception:
            pass


experiment_runner = ExperimentRunner()
