"""Evidence retrieval for the AI layer and the evidence search endpoint.

Case-scoped by construction: the caller passes the authorised case_id and every row comes from that case only.
Deterministic and dependency-free: BM25 over a per-evidence "search document" (reference, type + plain-language
type keywords, source, description, linked entity names, validity status), plus an exact-reference boost, a boost
for evidence linked to people/places named in the question, and light typo tolerance.

Retrieved text is still UNTRUSTED source content. Retrieval widens what the model may *cite*, never what it may *obey*,
and never crosses a case boundary. Non-SUPPORTED evidence is returned (investigators ask about it) but flagged.
"""
import difflib
import math
import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9]+")
REF = re.compile(r"\b[A-Za-z]{1,4}-[A-Za-z]{0,3}\d{1,5}\b")
STOP = set("""a an and are as at be been by can could did do does for from give has have how i in into is it its me my of on or
our please show tell that the their them there these this those to was we were what when where which who whom why will with
you your about any all find get list near around between during evidence record records item items relevant related
summarise summarize lead leads case cases ignore previous rules instructions instruction""".split())

# plain-language words -> the keywords stored in the search document for each evidence type
TYPE_KEYWORDS = {
    "GPS": "gps location movement tracking trail position",
    "CDR": "cdr call calls phone sms message messages communication contact",
    "CCTV": "cctv camera cameras footage video sighting",
    "TRANSACTION_RECORD": "bank transaction transactions payment payments money transfer account financial",
    "ACCESS_LOG": "access log door entry swipe card badge",
    "WITNESS_STATEMENT": "witness statement testimony neighbour said saw",
    "DOCUMENT": "document file report paper",
}
SYNONYMS = {w: kw.split()[0] for kw in TYPE_KEYWORDS.values() for w in kw.split()}

MAX_DOCS = 20000   # guard: a case this large needs an indexed (Postgres FTS / vector) retriever instead
K1, B = 1.5, 0.75


def tokenize(text: str) -> list[str]:
    return TOKEN.findall((text or "").lower())


def _load_docs(conn, case_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT e.evidence_id, e.ref, e.evidence_type, e.source, e.evidence_timestamp, e.description,
                  e.validity_status::text AS validity_status, e.reliability_score,
                  coalesce(array_agg(n.ref || '|' || n.display_name) FILTER (WHERE n.ref IS NOT NULL), '{}') AS ents
           FROM evidence e
           LEFT JOIN evidence_entities ee ON ee.case_id=e.case_id AND ee.evidence_id=e.evidence_id
           LEFT JOIN entities n ON n.case_id=ee.case_id AND n.entity_id=ee.entity_id
           WHERE e.case_id=%s GROUP BY e.evidence_id ORDER BY e.ref LIMIT %s""", (case_id, MAX_DOCS)).fetchall()
    docs = []
    for r in rows:
        ents = [x.split("|", 1) for x in r["ents"]]
        text = " ".join([r["ref"], r["evidence_type"].replace("_", " "), TYPE_KEYWORDS.get(r["evidence_type"], ""), r["source"],
                         r["description"] or "", " ".join(f"{a} {b}" for a, b in ents), r["validity_status"]])
        docs.append({**r, "entities": ents, "tokens": tokenize(text)})
    return docs


def _expand(question: str, vocab: set[str], typo: bool = True) -> tuple[list[str], dict[str, str]]:
    """Query terms: stop words removed, plain-language type words mapped, small typos corrected from the case vocabulary."""
    terms, fixed = [], {}
    for t in tokenize(question):
        if t in STOP or len(t) < 2:
            continue
        if typo and t not in vocab and len(t) >= 5 and not t.isdigit():
            near = difflib.get_close_matches(t, vocab, n=1, cutoff=0.8)
            if near:
                fixed[t], t = near[0], near[0]
        terms.append(t)
        if t in SYNONYMS and SYNONYMS[t] != t:
            terms.append(SYNONYMS[t])
    return terms, fixed


def search_evidence(conn, case_id: int, question: str, k: int = 8, *, entity_boost: bool = True, ref_boost: bool = True, typo: bool = True) -> dict:
    """entity_boost / ref_boost / typo default to True (the production behaviour); they exist so research can ablate each mechanism."""
    docs = _load_docs(conn, case_id)
    if not docs:
        return {"method": "bm25", "terms": [], "hits": []}
    n = len(docs)
    avg = sum(len(d["tokens"]) for d in docs) / n or 1.0
    df = Counter(t for d in docs for t in set(d["tokens"]))
    terms, fixed = _expand(question, set(df), typo)
    qrefs = {r.upper() for r in REF.findall(question)} if ref_boost else set()
    qlow = " " + " ".join(fixed.get(t, t) for t in tokenize(question)) + " "
    # people / places named in the question: full name or reference, matched on word boundaries
    named = {}
    for d in docs:
        for ref, name in d["entities"]:
            if entity_boost and ref not in named and (f" {' '.join(tokenize(name))} " in qlow or ref.upper() in qrefs):
                named[ref] = name
    hits = []
    for d in docs:
        tf = Counter(d["tokens"])
        score, matched = 0.0, []
        for t in set(terms):
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * len(d["tokens"]) / avg))
                matched.append(t)
        why = []
        if d["ref"].upper() in qrefs:
            score += 100.0
            why.append("exact reference")
        linked = [named[r] for r, _ in d["entities"] if r in named]
        if linked:
            score += 3.0 * len(linked)
            why.append("linked to " + ", ".join(sorted(set(linked))))
        if matched:
            why.append("terms: " + ", ".join(sorted(matched)))
        if score > 0 and (why):
            hits.append({"ref": d["ref"], "evidence_type": d["evidence_type"], "source": d["source"],
                         "evidence_timestamp": d["evidence_timestamp"], "validity_status": d["validity_status"],
                         "reliability_score": d["reliability_score"], "description": d["description"] or "",
                         "entities": [{"id": r, "name": nm} for r, nm in d["entities"]],
                         "score": round(score, 3), "matched_on": why})
    hits.sort(key=lambda h: (-h["score"], h["ref"]))
    return {"method": "bm25+entity+reference", "terms": sorted(set(terms)), "typo_corrections": fixed,
            "named_entities": sorted(named), "hits": hits[:max(1, min(k, 50))]}
