from research.phase3.algorithms import make as make3
from .q40r import Q40R
from .raeer import RAEER

PHASE4_NEW = ["q40_r", "raeer"]


def make(_algo, **kw):
    if _algo == "q40_r":
        return Q40R(**kw)
    if _algo == "raeer":
        return RAEER(**kw)
    return make3(_algo, **kw)
