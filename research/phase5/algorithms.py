"""Method registry for Phase 5: Phase 3/4 methods + RAEER ablations + Q40 python re-expression + sensitivity variants."""
from research.phase4.algorithms import Q40R, RAEER, make as make4

ABLATION = {
    "raeer-no_reliability": {"reliability": False}, "raeer-no_contradiction": {"contradiction": False}, "raeer-no_temporal": {"temporal": False},
    "raeer-no_graph": {"relational": False}, "raeer-no_lifecycle": {"lifecycle": False}, "raeer-no_corroboration": {"corroboration": False},
    "raeer-no_independence": {"independence": False}, "raeer-no_provenance": {"provenance": False},
}
Q40_SUPPORTED_ONLY = {"SUPPORTED": 1.0, "CHALLENGED": 0.0, "INVALIDATED": 0.0, "SUPERSEDED": 0.0}


def make(name, **kw):
    if name in ABLATION:
        return RAEER(features=ABLATION[name], name=name)
    if name == "raeer-no_spatial":
        return RAEER(weights={"spatial": 0.0}, name=name)
    if name == "raeer-no_communication":
        return RAEER(weights={"communication": 0.0}, name=name)
    if name == "q40_py":
        return Q40R(features={"reliability": False}, name="q40_py", status_factor=Q40_SUPPORTED_ONLY)
    if name.startswith("raeer@"):                       # sensitivity variants: "raeer@gamma=0.25" etc. (see sensitivity.py)
        from research.phase5.sensitivity import variant
        return variant(name)
    return make4(name, **kw)
