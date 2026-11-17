"""Experiment Service: high-level orchestrator for research experiments and comparisons."""
import json
import logging
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from .. import config
from .experiment_runner import experiment_runner
from .statistical_service import statistical_service

log = logging.getLogger("crimemind.research")


class ExperimentService:
    """Manages experiment records and multi-algorithm comparative studies."""

    def create_experiment(
        self,
        name: str,
        algorithm: str,
        dataset_id: str,
        seeds: List[int],
        config_json: Dict[str, Any],
        created_by: str = "admin",
    ) -> int:
        """Inserts a new experiment record in QUEUED state."""
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            row = conn.execute(
                """
                INSERT INTO research_experiments (
                    name, algorithm, dataset_id, seeds, config_json, status, created_by
                ) VALUES (%s, %s, %s, %s, %s, 'QUEUED', %s)
                RETURNING experiment_id
                """,
                (name, algorithm, dataset_id, seeds, json.dumps(config_json), created_by),
            ).fetchone()
            conn.commit()
            return row["experiment_id"]

    def get_experiment_status(self, experiment_id: int) -> Optional[Dict[str, Any]]:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            return conn.execute(
                "SELECT * FROM research_experiments WHERE experiment_id = %s",
                (experiment_id,),
            ).fetchone()

    def get_experiment_details(self, experiment_id: int) -> Optional[Dict[str, Any]]:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            exp = conn.execute(
                "SELECT * FROM research_experiments WHERE experiment_id = %s",
                (experiment_id,),
            ).fetchone()
            if not exp:
                return None

            metrics = conn.execute(
                "SELECT * FROM research_experiment_metrics WHERE experiment_id = %s ORDER BY metric_name",
                (experiment_id,),
            ).fetchall()

            seed_results = conn.execute(
                "SELECT * FROM research_experiment_seed_results WHERE experiment_id = %s ORDER BY seed, case_ref",
                (experiment_id,),
            ).fetchall()

            log_count = conn.execute(
                "SELECT count(*) as cnt FROM research_experiment_logs WHERE experiment_id = %s",
                (experiment_id,),
            ).fetchone()["cnt"]

            res = dict(exp)
            res["metrics"] = [dict(m) for m in metrics]
            res["seed_results"] = [
                {
                    "result_id": sr["result_id"],
                    "seed": sr["seed"],
                    "case_ref": sr["case_ref"],
                    "metrics": sr["metrics_json"] if isinstance(sr["metrics_json"], dict) else json.loads(sr["metrics_json"]),
                    "top_ranked": sr["top_ranked"] if isinstance(sr["top_ranked"], list) else json.loads(sr["top_ranked"]),
                    "n_candidates": sr["n_candidates"],
                    "n_relevant": sr["n_relevant"],
                }
                for sr in seed_results
            ]
            res["log_count"] = log_count
            return res

    def list_experiments(self, limit: int = 50, algorithm: Optional[str] = None) -> List[Dict[str, Any]]:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            if algorithm:
                rows = conn.execute(
                    """
                    SELECT e.*, count(m.metric_id) as metrics_count
                    FROM research_experiments e
                    LEFT JOIN research_experiment_metrics m ON e.experiment_id = m.experiment_id
                    WHERE e.algorithm = %s
                    GROUP BY e.experiment_id
                    ORDER BY e.created_at DESC LIMIT %s
                    """,
                    (algorithm, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT e.*, count(m.metric_id) as metrics_count
                    FROM research_experiments e
                    LEFT JOIN research_experiment_metrics m ON e.experiment_id = m.experiment_id
                    GROUP BY e.experiment_id
                    ORDER BY e.created_at DESC LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_experiment_logs(self, experiment_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT log_id, log_timestamp, level, message
                FROM research_experiment_logs
                WHERE experiment_id = %s
                ORDER BY log_id ASC LIMIT %s
                """,
                (experiment_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def cancel_experiment(self, experiment_id: int) -> bool:
        experiment_runner.request_cancel(experiment_id)
        with psycopg.connect(config.DATABASE_URL) as conn:
            conn.execute(
                "UPDATE research_experiments SET status = 'CANCELLED' WHERE experiment_id = %s AND status IN ('QUEUED', 'RUNNING')",
                (experiment_id,),
            )
            conn.commit()
        return True

    def run_comparative_study_sync(
        self,
        study_name: str,
        algorithms: List[str],
        seeds: List[int],
        cases_filter: Optional[List[str]],
        raeer_parameters: Optional[Dict[str, Any]],
        target_metrics: List[str],
    ) -> Dict[str, Any]:
        """Runs multiple algorithms on the exact same dataset seeds and performs statistical t-tests."""
        exp_ids = {}
        for algo in algorithms:
            params = raeer_parameters if "raeer" in algo.lower() else None
            exp_id = self.create_experiment(
                name=f"{study_name} - {algo.upper()}",
                algorithm=algo,
                dataset_id="synthetic_seeds",
                seeds=seeds,
                config_json={"cases": cases_filter, "parameters": params, "metrics": target_metrics},
            )
            exp_ids[algo] = exp_id
            # Execute synchronously in this background worker turn
            experiment_runner.run_experiment_sync(
                experiment_id=exp_id,
                algorithm_name=algo,
                dataset_id="synthetic_seeds",
                seeds=seeds,
                cases_filter=cases_filter,
                parameters=params,
                target_metrics=target_metrics,
            )

        # Retrieve completed results for comparison
        results_by_algo = {}
        for algo, exp_id in exp_ids.items():
            results_by_algo[algo] = self.get_experiment_details(exp_id)

        # Compute paired statistical tests across algorithms for primary metric (e.g. nDCG@5)
        stat_comparisons = []
        primary_metric = "nDCG@5"
        for i in range(len(algorithms)):
            for j in range(i + 1, len(algorithms)):
                a1 = algorithms[i]
                a2 = algorithms[j]
                r1 = results_by_algo.get(a1, {}).get("seed_results", [])
                r2 = results_by_algo.get(a2, {}).get("seed_results", [])

                vals1 = [sr["metrics"].get(primary_metric, 0.0) for sr in r1 if primary_metric in sr["metrics"]]
                vals2 = [sr["metrics"].get(primary_metric, 0.0) for sr in r2 if primary_metric in sr["metrics"]]

                t_res = statistical_service.paired_t_test(vals1, vals2)
                stat_comparisons.append({
                    "algo_a": a1,
                    "algo_b": a2,
                    "metric": primary_metric,
                    "mean_a": round(sum(vals1) / len(vals1), 4) if vals1 else 0.0,
                    "mean_b": round(sum(vals2) / len(vals2), 4) if vals2 else 0.0,
                    "test": t_res,
                })

        return {
            "study_name": study_name,
            "algorithms": algorithms,
            "experiment_ids": exp_ids,
            "results": results_by_algo,
            "statistical_comparisons": stat_comparisons,
        }


experiment_service = ExperimentService()
