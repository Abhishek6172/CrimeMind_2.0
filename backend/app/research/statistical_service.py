"""Statistical service: paired t-test and significance testing between algorithm runs."""
import math
from typing import Any, Dict, List, Tuple


class StatisticalService:
    """Performs rigorous statistical significance testing between research algorithms."""

    @staticmethod
    def paired_t_test(a_vals: List[float], b_vals: List[float]) -> Dict[str, Any]:
        """Calculates paired Student's t-test between two lists of matched seed observations."""
        n = min(len(a_vals), len(b_vals))
        if n < 2:
            return {
                "t_statistic": 0.0,
                "p_value": 1.0,
                "is_significant": False,
                "significance_label": "n.s. (insufficient samples)",
                "mean_diff": 0.0,
            }

        diffs = [a - b for a, b in zip(a_vals[:n], b_vals[:n])]
        mean_diff = sum(diffs) / n
        var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)

        if var_diff <= 1e-12:
            # Virtually identical
            return {
                "t_statistic": 0.0,
                "p_value": 1.0 if mean_diff == 0 else 0.0001,
                "is_significant": mean_diff != 0,
                "significance_label": "*** (p < 0.001)" if mean_diff != 0 else "n.s. (identical)",
                "mean_diff": round(mean_diff, 4),
            }

        se_diff = math.sqrt(var_diff / n)
        t_stat = mean_diff / se_diff
        df = n - 1

        # Approximation of two-tailed p-value for Student's t-distribution
        p_val = StatisticalService._approx_t_pvalue(abs(t_stat), df)

        if p_val < 0.001:
            sig_label = "*** (p < 0.001)"
            is_sig = True
        elif p_val < 0.01:
            sig_label = "** (p < 0.01)"
            is_sig = True
        elif p_val < 0.05:
            sig_label = "* (p < 0.05)"
            is_sig = True
        else:
            sig_label = f"n.s. (p = {p_val:.3f})"
            is_sig = False

        return {
            "t_statistic": round(t_stat, 4),
            "p_value": round(p_val, 5),
            "is_significant": is_sig,
            "significance_label": sig_label,
            "mean_diff": round(mean_diff, 4),
            "df": df,
        }

    @staticmethod
    def _approx_t_pvalue(t: float, df: int) -> float:
        """Approximates two-tailed p-value using standard normal / Cornish-Fisher approximation."""
        # Convert t to standard normal z approximation for large df or transform
        x = df / (df + t * t)
        # Beta incomplete approximation for Student t
        # Normal approximation for z = t * (1 - 1/(4*df)) / sqrt(1 + t^2/(2*df))
        z = t * (1.0 - 1.0 / (4.0 * df)) / math.sqrt(1.0 + (t * t) / (2.0 * df))
        # Two-tailed standard normal CDF: 2 * (1 - Phi(z))
        # Erf approximation
        p = math.erfc(z / math.sqrt(2.0))
        return max(0.0, min(1.0, p))


statistical_service = StatisticalService()
