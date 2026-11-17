"""Case-scoped, traceable reports (SRS Section 21). A report presents authorized records; it is not evidence."""
import hashlib
import html
import json
from datetime import datetime, timezone

from . import config
from .routers.analysis import fresh_run
from .sql_engine import jsonable


def build_report(conn, case: dict, user: str) -> dict:
    cid = case["case_id"]
    run = fresh_run(conn, case, user)
    q = lambda sql, *a: conn.execute(sql, a).fetchall()
    content = {
        "case": {"reference": case["case_ref"], "title": case["title"], "status": case["status"]},
        "generated_at": datetime.now(timezone.utc).isoformat(), "generated_by": user,
        "incidents": q("""SELECT e.ref, e.occurred_at, e.description, l.display_name AS location FROM events e LEFT JOIN entities l
                          ON l.case_id=e.case_id AND l.entity_id=e.location_entity_id WHERE e.case_id=%s AND e.event_type='INCIDENT'""", cid),
        "questions_performed": q("""SELECT question_id, module_id, module_version, status, result_count, executed_at, user_name, params
                                    FROM query_audit WHERE case_id=%s AND status IN ('OK','EMPTY') ORDER BY executed_at""", cid),
        "findings": q("""SELECT f.finding_key, f.version, f.statement, f.classification, f.status::text AS status, f.method,
                         coalesce((SELECT array_agg(e.ref || ' [' || e.validity_status::text || ']' ORDER BY e.ref) FROM finding_evidence_links l
                                   JOIN evidence e ON e.evidence_id=l.evidence_id AND e.case_id=l.case_id WHERE l.finding_id=f.finding_id), '{}') AS evidence
                         FROM findings f WHERE f.case_id=%s AND f.status<>'OUTDATED' ORDER BY f.classification, f.finding_key""", cid),
        "findings_history": q("""SELECT finding_key, version, status::text AS status, generated_at FROM findings WHERE case_id=%s AND status='OUTDATED'
                                 ORDER BY finding_key, version""", cid),
        "correlations": q("""SELECT c.ref, c.rule_id, c.rule_version, c.result_type, c.summary, c.uncertainties, c.thresholds, c.source_records
                             FROM correlations c WHERE c.case_id=%s AND c.run_id=%s AND c.result_type<>'FACT' ORDER BY c.result_type DESC, c.ref""", cid, run["run_id"]),
        "evidence": q("""SELECT ref, evidence_type, source, evidence_timestamp, validity_status::text AS validity_status, reliability_score
                         FROM evidence e WHERE case_id=%s AND (validity_status<>'SUPPORTED' OR EXISTS (SELECT 1 FROM finding_evidence_links l
                         JOIN findings f ON f.finding_id=l.finding_id WHERE l.evidence_id=e.evidence_id AND f.status<>'OUTDATED')) ORDER BY ref""", cid),
        "validity_history": q("""SELECT e.ref AS evidence, v.previous_status::text AS previous_status, v.new_status::text AS new_status,
                                 v.reason_code::text AS reason, v.changed_by, v.changed_at, t.ref AS triggering_evidence
                                 FROM evidence_validity_events v JOIN evidence e ON e.evidence_id=v.evidence_id AND e.case_id=v.case_id
                                 LEFT JOIN evidence t ON t.evidence_id=v.triggering_evidence_id AND t.case_id=v.case_id
                                 WHERE v.case_id=%s ORDER BY v.changed_at""", cid),
        "hypotheses": q("SELECT ref, title, status, needs_review FROM hypotheses WHERE case_id=%s ORDER BY ref", cid),
        "ai_assisted_synthesis": q("""SELECT analysis_id::text, question, provider, status, output, created_at FROM ai_analyses
                                      WHERE case_id=%s AND status='OK' ORDER BY created_at DESC LIMIT 3""", cid),
        "reviews": q("SELECT target_type, target_ref, decision, comment, reviewer, created_at FROM reviews WHERE case_id=%s ORDER BY created_at", cid),
        "limitations": [
            "Correlations and inferred patterns are leads for review; they do not establish intent, guilt or responsibility.",
            "Absence of a record does not establish that an event did not occur.",
            "AI-assisted text is labelled and separate from recorded facts; evidence with a validity state other than SUPPORTED is historical context only.",
            "Reliability scores are manually assigned heuristic weights, not probabilities.",
            "All data in this system is synthetic."],
        "version_meta": {"app_version": config.APP_VERSION, "correlation_run": run["run_id"],
                         "sql_modules": [r["module_id"] + "@" + r["version"] for r in q("SELECT module_id, version FROM sql_modules ORDER BY module_id")]},
    }
    content = jsonable(content)
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    row = conn.execute(
        "INSERT INTO reports(case_id, generated_by, content, content_sha256, version_meta) VALUES (%s,%s,%s::jsonb,%s,%s::jsonb) RETURNING report_id, generated_at",
        (cid, user, json.dumps(content), digest, json.dumps(content["version_meta"]))).fetchone()
    return {"report_id": str(row["report_id"]), "generated_at": row["generated_at"].isoformat(), "content_sha256": digest, "content": content}


def render_html(rep: dict) -> str:
    c, e = rep["content"], html.escape
    def tbl(rows, cols):
        if not rows:
            return "<p><em>None recorded.</em></p>"
        head = "".join(f"<th>{e(h)}</th>" for h in cols)
        body = "".join("<tr>" + "".join(f"<td>{e(', '.join(map(str, r.get(k))) if isinstance(r.get(k), list) else str(r.get(k, '')))}</td>" for k in cols) + "</tr>" for r in rows)
        return f"<table><tr>{head}</tr>{body}</table>"
    ai = "".join(f"<div class='ai'><strong>AI-ASSISTED (provider: {e(a['provider'])})</strong> — {e(a['question'])}<br>{e(a['output']['summary'])}</div>"
                 for a in c["ai_assisted_synthesis"]) or "<p><em>No AI-assisted synthesis included.</em></p>"
    return f"""<!doctype html><meta charset=utf-8><title>CrimeMind report {e(c['case']['reference'])}</title>
<style>body{{font:14px/1.5 system-ui;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}table{{border-collapse:collapse;width:100%;margin:.5rem 0}}
td,th{{border:1px solid #ccc;padding:4px 8px;text-align:left;font-size:12px;vertical-align:top}}th{{background:#f1f1f1}}.ai{{border-left:4px solid #b36b00;background:#fff7e8;padding:8px 12px;margin:8px 0}}
.note{{background:#eef3fb;padding:8px 12px}}</style>
<h1>{e(c['case']['title'])} <small>({e(c['case']['reference'])})</small></h1>
<p class=note>Decision-support report generated {e(c['generated_at'])} by {e(c['generated_by'])}. Report {e(rep['report_id'])} · SHA-256 {e(rep['content_sha256'][:16])}… ·
Synthetic data. This report is a presentation of records, not independent evidence.</p>
<h2>Incident</h2>{tbl(c['incidents'], ['ref','occurred_at','location','description'])}
<h2>Investigation questions performed</h2>{tbl(c['questions_performed'], ['question_id','module_id','module_version','status','result_count','executed_at','user_name'])}
<h2>Current findings</h2>{tbl(c['findings'], ['finding_key','version','classification','status','statement','evidence'])}
<h2>Correlations and inferred patterns (non-FACT)</h2>{tbl(c['correlations'], ['ref','rule_id','rule_version','result_type','summary','uncertainties'])}
<h2>Evidence and validity</h2>{tbl(c['evidence'], ['ref','evidence_type','source','validity_status','reliability_score'])}
<h2>Validity history</h2>{tbl(c['validity_history'], ['evidence','previous_status','new_status','reason','triggering_evidence','changed_by','changed_at'])}
<h2>Hypotheses (not recorded facts)</h2>{tbl(c['hypotheses'], ['ref','title','status','needs_review'])}
<h2>AI-assisted synthesis</h2>{ai}
<h2>Investigator reviews</h2>{tbl(c['reviews'], ['target_type','target_ref','decision','comment','reviewer','created_at'])}
<h2>Uncertainties and limitations</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in c['limitations'])}</ul>
<p><small>Versions: {e(json.dumps(c['version_meta']))}</small></p>"""
