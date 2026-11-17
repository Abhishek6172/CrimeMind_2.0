"""Criteria-Based Content Analysis (CBCA) & Statement Validity Assessment (SVA) Engine.
Extracts linguistic deception markers, sensory detail grounding, pronoun depersonalization,
temporal rigidity, cognitive load indicators, and cross-checks with case evidence.
"""

import math
import re
from typing import Any, Dict, List, Tuple


# =============================================================================
# Forensic Linguistic Lexicons & Heuristics
# =============================================================================

PRONOUNS_1ST_SINGULAR = {"i", "me", "my", "mine", "myself"}
PRONOUNS_1ST_PLURAL = {"we", "us", "our", "ours", "ourselves"}
PRONOUNS_3RD = {"he", "him", "his", "himself", "she", "her", "hers", "herself", "they", "them", "their", "theirs", "it", "its"}

SENSORY_VISUAL = {
    "see", "saw", "seen", "seeing", "sight", "look", "looked", "looking", "glance", "glanced",
    "stare", "dark", "pitch", "bright", "flash", "shadow", "shadows", "dim", "neon", "flicker",
    "flickering", "yellow", "red", "blue", "green", "black", "white", "silhouette", "glowing",
    "glare", "view", "witnessed", "spotted", "recognized", "spark"
}

SENSORY_AUDITORY = {
    "hear", "heard", "hearing", "sound", "sounds", "noise", "screamed", "scream", "shout", "shouted",
    "bang", "crash", "thud", "slam", "slammed", "whisper", "whispered", "silent", "silence",
    "loud", "hum", "humming", "buzzing", "alarm", "siren", "sirens", "yell", "yelling", "screech",
    "screeching", "footsteps", "rustling", "click", "rattle", "explosion", "muffled", "crying"
}

SENSORY_TACTILE = {
    "cold", "freezing", "hot", "burning", "warm", "wet", "slick", "slippery", "damp", "dry",
    "rough", "smooth", "sharp", "heavy", "light", "pain", "hurt", "shiver", "shivering", "grabbed",
    "pulled", "dragged", "sweat", "sweating", "blood", "bleeding", "bruise", "cut", "chilly", "icy"
}

SENSORY_OLFACTORY_GUSTATORY = {
    "smell", "smelled", "smelling", "scent", "odor", "stench", "perfume", "smoke", "smoking",
    "sulfur", "gunpowder", "gasoline", "petrol", "burning", "rotten", "taste", "tasted", "sour", "bitter"
}

ALL_SENSORY = SENSORY_VISUAL | SENSORY_AUDITORY | SENSORY_TACTILE | SENSORY_OLFACTORY_GUSTATORY

EQUIVOCATION_HEDGES = [
    "to be completely honest", "to tell you the truth", "honestly speaking", "in all honesty",
    "as god is my witness", "swear on my mother", "swear to god", "believe me", "trust me",
    "i would never in a million years", "truth be told", "i am an honest person", "i have no reason to lie"
]

SOFT_HEDGES = {
    "maybe", "perhaps", "probably", "possibly", "i guess", "i think", "i suppose",
    "as far as i recall", "if i recall correctly", "might have", "could have", "somewhat",
    "around that time", "kind of", "sort of", "more or less"
}

TEMPORAL_RIGID_CONNECTORS = {
    "first", "secondly", "then", "next", "after that", "afterward", "subsequently", "finally",
    "later on", "thereafter"
}

TEMPORAL_SKIPS = [
    "next thing i know", "next thing i knew", "before i knew it", "and then later",
    "some time passed", "after a while", "suddenly out of nowhere", "all of a sudden"
]

SPONTANEOUS_CORRECTIONS = [
    "wait", "actually", "no wait", "let me correct that", "i mean", "what i meant was",
    "thinking back", "now that i think about it", "not really", "correction"
]

ADMITTING_LACK_OF_MEMORY = [
    "i don't remember", "i cannot recall", "i can't be sure", "i blacked out",
    "i lost track of time", "my memory is hazy", "i'm not certain", "i couldn't see clearly"
]

PASSIVE_VOICE_PATTERNS = [
    r"\b(?:was|were|is|are|been|being)\s+(?:placed|taken|seen|shot|moved|opened|broken|found|damaged|carried|fired|done|driven)\b",
    r"\ba\s+(?:gun|weapon|knife|shot|break-in|incident|fire)\s+(?:occurred|happened|went off|took place)\b"
]


class CBCAAnalyzer:
    """Forensic Linguistic and CBCA Statement Credibility Evaluator."""

    def __init__(self):
        pass

    def analyze(
        self,
        text: str,
        case_evidence: List[Dict[str, Any]] = None,
        case_entities: List[Dict[str, Any]] = None,
        subject_name: str = "Subject",
    ) -> Dict[str, Any]:
        """Performs full forensic credibility analysis on the statement transcript."""
        case_evidence = case_evidence or []
        case_entities = case_entities or []

        # 1. Segment into sentences
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if not raw_sentences:
            raw_sentences = [text.strip()]

        total_words = len(re.findall(r"\b\w+\b", text))
        if total_words == 0:
            total_words = 1

        # 2. Extract global metrics
        text_lower = text.lower()
        words_lower = re.findall(r"\b\w+\b", text_lower)

        # Lexical counters
        count_1st_sing = sum(1 for w in words_lower if w in PRONOUNS_1ST_SINGULAR)
        count_1st_plur = sum(1 for w in words_lower if w in PRONOUNS_1ST_PLURAL)
        count_3rd = sum(1 for w in words_lower if w in PRONOUNS_3RD)

        # Passive voice instances
        passive_matches = []
        for pat in PASSIVE_VOICE_PATTERNS:
            passive_matches.extend(re.findall(pat, text_lower))
        count_passives = len(passive_matches)

        # Depersonalization score
        # High ratio of 3rd person + passives relative to 1st person indicates distancing
        depersonalization_ratio = (count_3rd + count_passives * 1.5) / max(1, count_1st_sing + count_1st_plur)

        # Sensory detail analysis
        sensory_visual_words = [w for w in words_lower if w in SENSORY_VISUAL]
        sensory_auditory_words = [w for w in words_lower if w in SENSORY_AUDITORY]
        sensory_tactile_words = [w for w in words_lower if w in SENSORY_TACTILE]
        sensory_olfactory_words = [w for w in words_lower if w in SENSORY_OLFACTORY_GUSTATORY]
        all_sensory_found = sensory_visual_words + sensory_auditory_words + sensory_tactile_words + sensory_olfactory_words

        sensory_density_pct = round((len(all_sensory_found) / total_words) * 100, 2)

        # Equivocation and over-justification hedges
        equivocations_found = [h for h in EQUIVOCATION_HEDGES if h in text_lower]
        soft_hedges_found = [w for w in words_lower if w in SOFT_HEDGES]
        temporal_skips_found = [ts for ts in TEMPORAL_SKIPS if ts in text_lower]
        corrections_found = [c for c in SPONTANEOUS_CORRECTIONS if c in text_lower]
        admit_memory_found = [m for m in ADMITTING_LACK_OF_MEMORY if m in text_lower]

        # 3. Sentence-by-Sentence Breakdown
        sentence_analyses = []
        total_sentence_credibility = 0.0
        total_sentence_cognitive_load = 0.0

        for idx, s_text in enumerate(raw_sentences):
            s_lower = s_text.lower()
            s_words = re.findall(r"\b\w+\b", s_lower)
            s_word_count = len(s_words) or 1

            s_flags = []
            s_sensory = [w for w in s_words if w in ALL_SENSORY]
            s_hedges = [h for h in EQUIVOCATION_HEDGES if h in s_lower] + [w for w in s_words if w in SOFT_HEDGES]
            s_corrections = [c for c in SPONTANEOUS_CORRECTIONS if c in s_lower]
            s_memory_lacks = [m for m in ADMITTING_LACK_OF_MEMORY if m in s_lower]

            # Cross-check evidence conflicts in this sentence
            s_conflicts = self._check_sentence_evidence_conflicts(s_lower, case_evidence, case_entities)

            # Calculate Sentence Credibility (Base 70)
            s_cred = 70.0

            # Rewards for genuine CBCA criteria
            if s_sensory:
                s_cred += min(20.0, len(s_sensory) * 6.0)
                s_flags.append(f"Sensory Grounding ({len(s_sensory)} perceptual cue{'s' if len(s_sensory)>1 else ''})")
            if s_corrections:
                s_cred += 12.0
                s_flags.append("Spontaneous Self-Correction (High Veracity Indicator)")
            if s_memory_lacks:
                s_cred += 10.0
                s_flags.append("Admitting Memory Limits (CBCA Criterion 15)")

            # Penalties for deception markers
            if any(h in s_lower for h in EQUIVOCATION_HEDGES):
                s_cred -= 30.0
                s_flags.append("Over-Justification Credibility Claim ('honest / swear')")
            if any(ts in s_lower for ts in TEMPORAL_SKIPS):
                s_cred -= 20.0
                s_flags.append("Temporal Narrative Skip (Glossed-over interval)")
            if len([w for w in s_words if w in SOFT_HEDGES]) >= 2:
                s_cred -= 15.0
                s_flags.append("Excessive Hedging / Evasion")

            # Evidence conflict penalties
            if s_conflicts:
                s_cred -= 40.0 * len(s_conflicts)
                for conf in s_conflicts:
                    s_flags.append(f"CONTRADICTION with Exhibit {conf['evidence_ref']}")

            s_cred = max(5.0, min(98.0, s_cred))

            # Calculate Sentence Cognitive Load (0 - 100)
            # High cognitive load indicated by length + hedging + passive avoidance
            c_load = 30.0
            if s_word_count > 25:
                c_load += 20.0
            if s_hedges:
                c_load += len(s_hedges) * 12.0
            if s_conflicts:
                c_load += 30.0
            if any(re.search(pat, s_lower) for pat in PASSIVE_VOICE_PATTERNS):
                c_load += 18.0
                s_flags.append("Passive Voice Depersonalization Shift")

            c_load = max(10.0, min(95.0, c_load))

            # Determine Status
            if s_conflicts:
                s_status = "CONTRADICTORY"
            elif s_cred < 45.0 or c_load > 75.0:
                s_status = "DECEPTIVE"
            elif s_cred < 60.0 or c_load > 60.0:
                s_status = "STRAINED"
            elif s_cred >= 75.0:
                s_status = "VERACIOUS"
            else:
                s_status = "NEUTRAL"

            sentence_analyses.append({
                "sentence_idx": idx + 1,
                "text": s_text,
                "word_count": s_word_count,
                "credibility_score": round(s_cred, 1),
                "cognitive_load_score": round(c_load, 1),
                "status": s_status,
                "flags": s_flags,
                "sensory_words": s_sensory,
                "hedges": s_hedges,
                "evidence_conflicts": s_conflicts,
            })

            total_sentence_credibility += s_cred
            total_sentence_cognitive_load += c_load

        # 4. Global Composite Credibility Score
        avg_sentence_cred = total_sentence_credibility / max(1, len(sentence_analyses))
        avg_sentence_load = total_sentence_cognitive_load / max(1, len(sentence_analyses))

        # Overall composite
        credibility_score = avg_sentence_cred
        # Global penalties
        if equivocations_found:
            credibility_score -= len(equivocations_found) * 10.0
        if depersonalization_ratio > 1.8:
            credibility_score -= 12.0
        if temporal_skips_found:
            credibility_score -= len(temporal_skips_found) * 8.0

        # Global rewards
        if sensory_density_pct > 3.5:
            credibility_score += 10.0
        if corrections_found:
            credibility_score += 8.0
        if admit_memory_found:
            credibility_score += 6.0

        credibility_score = round(max(5.0, min(96.0, credibility_score)), 1)
        cognitive_load_score = round(max(15.0, min(95.0, avg_sentence_load)), 1)

        # Credibility Classification Band
        if credibility_score >= 72.0:
            credibility_band = "HIGH_VERACITY"
        elif credibility_score >= 48.0:
            credibility_band = "AMBIGUOUS"
        else:
            credibility_band = "DECEPTIVE_INDICATORS"

        # 5. Radar Spider Dimensions (0 to 100 scale)
        radar_dimensions = {
            "sensory_density": min(100.0, round(sensory_density_pct * 18.0, 1)),
            "self_ownership": max(10.0, min(100.0, round(100.0 - depersonalization_ratio * 25.0, 1))),
            "temporal_spontaneity": max(10.0, min(100.0, round(85.0 - len(temporal_skips_found) * 20.0 + len(corrections_found) * 10.0, 1))),
            "hedging_filter": max(10.0, min(100.0, round(95.0 - (len(equivocations_found) * 25.0 + len(soft_hedges_found) * 3.5), 1))),
            "memory_grounding": min(100.0, round(30.0 + len(corrections_found) * 20.0 + len(admit_memory_found) * 18.0 + len(all_sensory_found) * 2.0, 1)),
            "evidence_concordance": max(5.0, min(100.0, round(95.0 - sum(len(sa["evidence_conflicts"]) for sa in sentence_analyses) * 35.0, 1))),
        }

        # 6. Generate Tactical Interrogation Questions
        tactical_questions = self._generate_tactical_questions(
            sentence_analyses,
            case_evidence,
            subject_name,
            equivocations_found,
            temporal_skips_found,
            sensory_density_pct,
        )

        return {
            "credibility_score": credibility_score,
            "credibility_band": credibility_band,
            "cognitive_load_score": cognitive_load_score,
            "metrics": {
                "total_words": total_words,
                "sentence_count": len(sentence_analyses),
                "sensory_words_count": len(all_sensory_found),
                "sensory_density_pct": sensory_density_pct,
                "first_person_pronouns": count_1st_sing + count_1st_plur,
                "third_person_pronouns": count_3rd,
                "passive_voice_count": count_passives,
                "depersonalization_ratio": round(depersonalization_ratio, 2),
                "equivocation_hedges_count": len(equivocations_found),
                "soft_hedges_count": len(soft_hedges_found),
                "temporal_skips_count": len(temporal_skips_found),
                "spontaneous_corrections_count": len(corrections_found),
                "memory_limitation_admissions": len(admit_memory_found),
            },
            "sentence_analyses": sentence_analyses,
            "tactical_questions": tactical_questions,
            "radar_dimensions": radar_dimensions,
        }

    def _check_sentence_evidence_conflicts(
        self,
        sentence_lower: str,
        case_evidence: List[Dict[str, Any]],
        case_entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Scans sentence against evidence descriptions and entity timelines for factual contradictions."""
        conflicts = []

        # Check for location alibi denials vs physical exhibits
        # E.g. "never left home" or "nowhere near green park" or "never set foot"
        denies_presence = any(
            phrase in sentence_lower
            for phrase in ["nowhere near", "never left", "never set foot", "inside the booth", "came straight back", "didn't see"]
        )

        if denies_presence:
            for ev in case_evidence:
                ev_desc = (ev.get("description") or "").lower()
                ev_ref = ev.get("ref", "E-EXHIBIT")

                # If evidence records CCTV or GPS presence of suspect
                if any(k in ev_desc for k in ["cctv", "camera", "footage", "sighting", "observed", "detected", "badge", "entered"]):
                    # Flag collision if sentence denies being in the area
                    if "green park" in sentence_lower and ("green park" in ev_desc or "gazebo" in ev_desc or "cam" in ev_desc):
                        conflicts.append({
                            "evidence_ref": ev_ref,
                            "conflict_type": "SPATIAL_ALIBI_CONTRADICTION",
                            "evidence_summary": ev.get("description", ""),
                            "reason": f"Subject statement denies presence at Green Park, directly contradicting forensic exhibit {ev_ref} confirming sighting.",
                        })
                    elif "warehouse" in sentence_lower and ("warehouse" in ev_desc or "gate" in ev_desc or "dock" in ev_desc):
                        conflicts.append({
                            "evidence_ref": ev_ref,
                            "conflict_type": "SPATIAL_ALIBI_CONTRADICTION",
                            "evidence_summary": ev.get("description", ""),
                            "reason": f"Subject claims complete inactivity, directly contradicted by {ev_ref} logging unauthorized entry activity.",
                        })

        # Check for weapon denials vs ballistic / forensic weapon recovery
        if "don't own any weapon" in sentence_lower or "no weapon" in sentence_lower or "never touched" in sentence_lower:
            for ev in case_evidence:
                ev_desc = (ev.get("description") or "").lower()
                if any(k in ev_desc for k in ["weapon", "firearm", "bullet", "casing", "knife", "ballistics", "residue"]):
                    conflicts.append({
                        "evidence_ref": ev.get("ref", "E-WEAPON"),
                        "conflict_type": "PHYSICAL_EXHIBIT_CONTRADICTION",
                        "evidence_summary": ev.get("description", ""),
                        "reason": f"Subject denies weapon involvement, conflicting with ballistic / physical forensic exhibit {ev.get('ref')}.",
                    })
                    break

        return conflicts

    def _generate_tactical_questions(
        self,
        sentences: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]],
        subject_name: str,
        equivocations: List[str],
        temporal_skips: List[str],
        sensory_density: float,
    ) -> List[Dict[str, Any]]:
        """Synthesizes strategic P.E.A.C.E. interview questions targeting cognitive vulnerabilities."""
        questions = []

        # 1. Reverse Chronology Cognitive Overload Technique
        if temporal_skips:
            questions.append({
                "category": "REVERSE_CHRONOLOGY",
                "question": f"Starting from when the morning sirens woke you, walk me backward hour by hour to when you purchased cigarettes.",
                "rationale": "Fabricated narratives are rehearsed in strict forward chronological order. Recounting backward exhausts cognitive reserves, causing scripted alibis to fracture.",
                "expected_truthful_response": "Pauses naturally to reconstruct episodic memory; describes sensory anchor points in reverse.",
                "expected_deceptive_reaction": "Severe hesitation, timeline contradictions, agitation, or refusal to reverse the narrative order.",
                "relevant_evidence_ref": None,
            })

        # 2. Sensory Depth Probe
        if sensory_density < 2.5:
            questions.append({
                "category": "SENSORY_PROBE",
                "question": f"Describe the weather, ambient lighting, and background sounds during the five minutes you stepped outside near the station.",
                "rationale": "Genuine memories contain incidental sensory background data. Deceptive accounts focus solely on simple action alibis and cannot invent coherent sensory layers spontaneously.",
                "expected_truthful_response": "Recalls specific perceptual details (cold wind, neon signs, traffic sounds, wet pavement).",
                "expected_deceptive_reaction": "Generic or evasive replies ('It was just normal', 'I wasn't paying attention to that').",
                "relevant_evidence_ref": None,
            })

        # 3. Evidence Discrepancy Trap
        contradictory_sentences = [s for s in sentences if s["evidence_conflicts"]]
        if contradictory_sentences:
            first_conflict = contradictory_sentences[0]["evidence_conflicts"][0]
            questions.append({
                "category": "EVIDENCE_DISCREPANCY",
                "question": f"If an optic camera or witness placed you within 50 meters of the central pavilion at 22:14, how would you account for that?",
                "rationale": f"Confronts the subject with Exhibit {first_conflict['evidence_ref']} without revealing the exact angle or frame resolution, forcing an alibi adjustment.",
                "expected_truthful_response": "Direct curiosity or immediate logical explanation ('Did someone mistake my jacket?').",
                "expected_deceptive_reaction": "Micro-expressions of shock, sudden posture shifting, throat clearing, or shifting blame ('Someone is framing me').",
                "relevant_evidence_ref": first_conflict["evidence_ref"],
            })

        # 4. Equivocation & Over-Justification Probe
        if equivocations:
            questions.append({
                "category": "COGNITIVE_OVERLOAD",
                "question": f"You mentioned 'to be completely honest' and 'swear to God'. What specific aspect of your evening timeline makes you concerned we won't believe you?",
                "rationale": "Highlights the subject's unsolicited credibility bolsters, forcing them to justify why they felt compelled to emphasize their honesty.",
                "expected_truthful_response": "Frustration with being suspected without over-the-top moral declarations.",
                "expected_deceptive_reaction": "Doubling down on moral character defenses rather than factual details.",
                "relevant_evidence_ref": None,
            })

        # Fallback standard P.E.A.C.E. question if few triggers
        if len(questions) < 2:
            questions.append({
                "category": "COGNITIVE_OVERLOAD",
                "question": f"Without repeating your previous summary, tell me everything that went through your mind between 21:00 and 22:30.",
                "rationale": "Accesses subjective internal mental state (CBCA Criterion 12). Truthful subjects easily recount feelings of boredom, frustration, or specific thoughts.",
                "expected_truthful_response": "Shares authentic internal monologues and incidental feelings.",
                "expected_deceptive_reaction": "Repeats the same bare action sequence with minimal psychological depth.",
                "relevant_evidence_ref": None,
            })

        return questions
