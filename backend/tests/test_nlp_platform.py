"""Unit tests for the Statement Credibility & Cognitive Load NLP Analyzer."""

from app.nlp.cbca_analyzer import CBCAAnalyzer


def test_cbca_truthful_statement():
    analyzer = CBCAAnalyzer()
    truthful_text = (
        "I was walking my dog near the east pavilion around ten past ten. "
        "It was freezing cold and the ground was slick with wet leaves from the afternoon drizzle. "
        "The halogen park lamps were flickering, making that awful humming sound like they always do. "
        "I heard loud muffled shouting near the gazebo—a man's voice, very harsh and agitated, "
        "then a sharp thud like something heavy hit the wooden benches. "
        "Wait, actually, he stumbled over the curb first before running. "
        "I can't be sure of his face because the hood was pulled low."
    )

    res = analyzer.analyze(truthful_text, subject_name="Ananya Sharma")
    assert res["credibility_score"] >= 70.0
    assert res["credibility_band"] == "HIGH_VERACITY"
    assert res["metrics"]["sensory_density_pct"] > 3.0
    assert res["metrics"]["spontaneous_corrections_count"] >= 1
    assert res["metrics"]["memory_limitation_admissions"] >= 1
    assert len(res["sentence_analyses"]) == 6
    assert len(res["tactical_questions"]) > 0


def test_cbca_deceptive_statement_with_contradiction():
    analyzer = CBCAAnalyzer()
    deceptive_text = (
        "To be completely honest with you, I was nowhere near Green Park that evening. "
        "As God is my witness, I came straight back to my flat around eight thirty. "
        "Then next thing I know, the morning sirens woke me up. "
        "The weapon? I don't own any weapon, someone must have planted that idea."
    )

    mock_evidence = [
        {"ref": "E-0285", "description": "CCTV camera CAM-05 footage at Green Park Gazebo showing subject at 22:14 UTC"},
        {"ref": "E-0089", "description": "Recovered weapon .32 caliber revolver with ballistic match"},
    ]

    res = analyzer.analyze(deceptive_text, case_evidence=mock_evidence, subject_name="Karan Bhatt")
    assert res["credibility_score"] < 50.0
    assert res["credibility_band"] == "DECEPTIVE_INDICATORS"
    assert res["metrics"]["equivocation_hedges_count"] >= 1

    # Check evidence conflict detection
    conflicts_found = []
    for sa in res["sentence_analyses"]:
        conflicts_found.extend(sa["evidence_conflicts"])

    assert len(conflicts_found) >= 1
    assert any(c["evidence_ref"] == "E-0285" for c in conflicts_found)


if __name__ == "__main__":
    test_cbca_truthful_statement()
    test_cbca_deceptive_statement_with_contradiction()
    print("All CBCA Forensic NLP tests passed successfully!")
