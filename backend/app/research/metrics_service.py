"""Metrics service: exact ranking metric evaluation and multi-seed statistical aggregation."""
import math
from typing import Any, Dict, List, Optional
from research.phase3.metrics.ranking_metrics import evaluate_ranking, METRIC_NAMES


class MetricsService:
    """Computes exact metrics against ground truth and performs statistical aggregation."""

    @staticmethod
    def evaluate(ranked_candidates: List[str], relevance_grades: Dict[str, int]) -> Dict[str, Any]:
        """Runs the exact ranking evaluator against ground-truth relevance grades."""
        raw_metrics = evaluate_ranking(ranked_candidates, relevance_grades)
        # Format metrics cleanly
        res = {}
        for k, v in raw_metrics.items():
            if isinstance(v, float):
                res[k] = round(v, 4)
            else:
                res[k] = v
        return res

    @staticmethod
    def aggregate_metrics(seed_case_results: List[Dict[str, Any]], target_metrics: List[str]) -> List[Dict[str, Any]]:
        """Aggregates metrics across all seed/case runs into mean, std_dev, std_err, 95% CI."""
        summaries = []
        n_samples = len(seed_case_results)
        if n_samples == 0:
            return summaries

        for m_name in target_metrics:
            # Collect valid numerical values
            vals = [
                float(r["metrics"][m_name])
                for r in seed_case_results
                if m_name in r["metrics"] and r["metrics"][m_name] is not None
            ]

            if not vals:
                continue

            n = len(vals)
            mean_val = sum(vals) / n
            min_val = min(vals)
            max_val = max(vals)

            if n > 1:
                variance = sum((x - mean_val) ** 2 for x in vals) / (n - 1)
                std_dev = math.sqrt(variance)
                std_err = std_dev / math.sqrt(n)
                # 95% confidence interval (z ~ 1.96)
                ci_lower = max(0.0, mean_val - 1.96 * std_err)
                ci_upper = min(1.0, mean_val + 1.96 * std_err)
            else:
                std_dev = 0.0
                std_err = 0.0
                ci_lower = mean_val
                ci_upper = mean_val

            summaries.append({
                "metric_name": m_name,
                "mean_value": round(mean_val, 4),
                "std_dev": round(std_dev, 4),
                "std_err": round(std_err, 4),
                "ci_lower": round(ci_lower, 4),
                "ci_upper": round(ci_upper, 4),
                "min_value": round(min_val, 4),
                "max_value": round(max_val, 4),
            })

        return summaries


metrics_service = MetricsService()
