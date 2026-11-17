"""Experiment configuration and algorithm instantiation factory."""
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from research.phase4.algorithms import Q40R, RAEER
from research.phase5.algorithms import make as make_algo_p5

ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "research" / "phase4" / "configs"


class ExperimentConfigManager:
    """Manages baseline and custom hyperparameter configurations."""

    @staticmethod
    def get_base_p4_config() -> Dict[str, Any]:
        cfg_path = CONFIG_DIR / "phase4_config.json"
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def instantiate_algorithm(algo_name: str, parameters: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, Any]]:
        """Instantiates the genuine algorithm and prepares the merged configuration dictionary."""
        base_cfg = ExperimentConfigManager.get_base_p4_config()
        algo_lower = algo_name.lower().strip()

        if algo_lower in ("raeer", "raeer_custom"):
            weights = None
            override = {}
            cfg = dict(base_cfg)

            if parameters:
                # 1. Weights
                if "weights" in parameters and isinstance(parameters["weights"], dict):
                    raw_w = parameters["weights"]
                    tot = sum(float(v) for v in raw_w.values())
                    if tot > 0:
                        weights = {k: float(v) / tot for k, v in raw_w.items()}
                        cfg["raeer"]["weights"] = weights

                # 2. Contradiction
                if "contradiction" in parameters and isinstance(parameters["contradiction"], dict):
                    c_params = parameters["contradiction"]
                    if "gamma" in c_params:
                        override.setdefault("contradiction", {})["gamma"] = float(c_params["gamma"])
                        cfg["raeer"]["contradiction"]["gamma"] = float(c_params["gamma"])
                    if "distance_m" in c_params:
                        override.setdefault("contradiction", {})["distance_m"] = float(c_params["distance_m"])
                        cfg["raeer"]["contradiction"]["distance_m"] = float(c_params["distance_m"])

                # 3. Temporal tau decay
                if "temporal_tau_minutes" in parameters:
                    val = float(parameters["temporal_tau_minutes"])
                    override["temporal_tau_minutes"] = val
                    cfg["raeer"]["temporal_tau_minutes"] = val

                # 4. Scene radius
                if "scene_radius_m" in parameters:
                    val = float(parameters["scene_radius_m"])
                    override["scene_radius_m"] = val
                    cfg["raeer"]["scene_radius_m"] = val

                # 5. Corroboration cap
                if "corroboration_domains_cap" in parameters:
                    val = int(parameters["corroboration_domains_cap"])
                    override["corroboration_domains_cap"] = val
                    cfg["raeer"]["corroboration_domains_cap"] = val

                # 6. Feature flags
                if "features" in parameters and isinstance(parameters["features"], dict):
                    override["features"] = parameters["features"]
                    cfg["raeer"]["features"].update(parameters["features"])

                # 7. Status factors
                if "status_factor" in parameters and isinstance(parameters["status_factor"], dict):
                    cfg["status_factor"].update(parameters["status_factor"])

            algo = RAEER(name="raeer", weights=weights, override=override)
            return algo, cfg

        elif algo_lower in ("q40", "q40_py", "q40_baseline"):
            algo = make_algo_p5("q40_py")
            return algo, base_cfg

        elif algo_lower in ("q40_r", "q40r"):
            algo = Q40R(name="q40_r")
            return algo, base_cfg

        else:
            # Check ablations or phase 5 variants
            algo = make_algo_p5(algo_name)
            return algo, base_cfg


config_manager = ExperimentConfigManager()
