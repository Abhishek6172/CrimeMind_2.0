"""Output validation pipeline: schema -> evidence reference -> classification -> safety (SRS 13.20). Application-level,
independent of prompt wording."""
import re

CLASSES = {"RECORDED FACT", "CORRELATED", "AI-INFERRED", "UNCERTAIN"}
ID_RE = re.compile(r"\b(?:E-[DN]?\d+|C-\d{3,5}|COMM-\d+|TXN-\d+|OBS-N?\d+|REL-\d+|EVT-\d+|[PVLDO]-[A-Z]*\d+)\b")
GUILT = re.compile(r"\b(?:is|are|was|were|be|being|proved|proven|clearly)\s+(?:the\s+)?(?:guilty|killer|murderer|culprit|perpetrator|criminal|responsible for)\b"
                   r"|\bcommitted\s+(?:the\s+)?(?:crime|murder|offen[cs]e|homicide)\b|\bconvicted\b|\bguilt\s+(?:is|has been)\s+(?:established|proven)"
                   r"|\b(?:planned|conspired|colluded)\b", re.I)
FACT_OVERREACH = re.compile(r"\b(?:together|knowingly|met with|worked with|were working|acted together)\b", re.I)


def validate(output, ctx: dict) -> list[str]:
    problems: list[str] = []
    allowed = ctx["_allowed"]
    known_ids = set(allowed["evidence"]) | set(allowed["correlations"]) | set(allowed["entities"]) | set(allowed["incident_refs"])
    ev_state = {e["id"]: e["validity_status"] for e in ctx["evidence"]}
    corr_cls = {c["id"]: c["classification"] for c in ctx["correlations"]}
    if not isinstance(output, dict):
        return ["output is not an object"]
    if not isinstance(output.get("summary"), str) or not output["summary"].strip():
        problems.append("summary missing")
    if not isinstance(output.get("uncertainties"), list) or not all(isinstance(u, str) for u in output.get("uncertainties", [])):
        problems.append("uncertainties must be a list of strings")
    conf = output.get("confidence")
    if conf is not None and not (isinstance(conf, (int, float)) and 0 <= conf <= 1):
        problems.append("confidence must be null or between 0 and 1")
    findings = output.get("findings")
    if not isinstance(findings, list):
        return problems + ["findings must be a list"]
    texts = [output.get("summary", "")] + [str(u) for u in output.get("uncertainties", []) if isinstance(u, str)]
    for i, f in enumerate(findings):
        tag = f"finding {i + 1}"
        if not isinstance(f, dict) or not isinstance(f.get("statement"), str):
            problems.append(f"{tag}: malformed")
            continue
        texts.append(f["statement"])
        cls = f.get("classification")
        if cls not in CLASSES:
            problems.append(f"{tag}: classification '{cls}' is not allowed")
            continue
        eids, cids = f.get("evidence_ids") or [], f.get("correlation_ids") or []
        if not isinstance(eids, list) or not isinstance(cids, list):
            problems.append(f"{tag}: evidence_ids/correlation_ids must be lists")
            continue
        for e in eids:
            if e not in allowed["evidence"]:
                problems.append(f"{tag}: evidence id '{e}' is not in the authorized context")
        for c in cids:
            if c not in allowed["correlations"]:
                problems.append(f"{tag}: correlation id '{c}' is not in the authorized context")
        for x in ID_RE.findall(f["statement"]):
            if x not in known_ids and not re.match(r"^(?:COMM|TXN|OBS|REL)-", x):
                problems.append(f"{tag}: statement mentions identifier '{x}' that is not in the context")
        if cls == "RECORDED FACT" and not (eids or cids):
            problems.append(f"{tag}: RECORDED FACT must cite supporting records")
        if cls == "CORRELATED" and not any(corr_cls.get(c) == "CORRELATED" for c in cids):
            problems.append(f"{tag}: CORRELATED must cite a CORRELATED correlation from the context")
        if cls == "AI-INFERRED" and not (eids or cids):
            problems.append(f"{tag}: AI-INFERRED must cite the records it is based on")
        if cls == "RECORDED FACT" and FACT_OVERREACH.search(f["statement"]):
            problems.append(f"{tag}: a correlation or inference was presented as a recorded fact")
        if cls in ("RECORDED FACT", "CORRELATED"):
            bad = [e for e in eids if ev_state.get(e, "SUPPORTED") != "SUPPORTED"]
            if bad:
                problems.append(f"{tag}: relies on evidence that is not currently SUPPORTED ({', '.join(bad)})")
    for t in texts:
        if GUILT.search(t):
            problems.append("output asserts guilt, intent or a legal conclusion")
            break
    return problems
