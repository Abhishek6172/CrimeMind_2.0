"""One-at-a-time sensitivity of RAEER to its parameters (names look like 'raeer@gamma=0.25')."""
import json
from pathlib import Path

from research.phase4.algorithms import RAEER

CFG5 = json.load(open(Path(__file__).parent / "configs" / "phase5_config.json"))
BASE_W = json.load(open(Path(__file__).resolve().parents[1] / "phase4/configs/phase4_config.json"))["raeer"]["weights"]


def names():
    s = CFG5["sensitivity"]
    out = [f"raeer@gamma={g}" for g in s["gamma"]] + [f"raeer@tau={t}" for t in s["tau_minutes"]] + [f"raeer@radius={r}" for r in s["scene_radius_m"]] \
        + [f"raeer@distance={d}" for d in s["contradiction_distance_m"]]
    out += [f"raeer@w_{k}={f}" for k in BASE_W for f in s["weight_scale"]]
    return out


def variant(name):
    key, val = name[len("raeer@"):].split("=")
    v = float(val)
    if key == "gamma":
        return RAEER(name=name, override={"contradiction": {"gamma": v}})
    if key == "tau":
        return RAEER(name=name, override={"temporal_tau_minutes": v})
    if key == "radius":
        return RAEER(name=name, override={"scene_radius_m": v})
    if key == "distance":
        return RAEER(name=name, override={"contradiction": {"distance_m": v}})
    if key.startswith("w_"):
        k = key[2:]
        w = dict(BASE_W); w[k] = w[k] * v
        tot = sum(w.values())
        return RAEER(name=name, weights={a: b / tot for a, b in w.items()})
    raise KeyError(name)
