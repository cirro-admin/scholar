"""
writing_workflow/evaluator.py
──────────────────────────────
LLM judge + quality scorer with humanization weighting.
"""

from __future__ import annotations
import textwrap
from dataclasses import dataclass

from utils.llm import generate_json
from config.modes import OutputModeConfig
from writing_workflow.section_drafter import DraftedSection

AI_SIGNATURE_PHRASES = [
    "in today's rapidly evolving","it is worth noting","it's important to note",
    "in the realm of","delve into","multifaceted","it is clear that",
    "in conclusion, this","overall, it is","straightforward","utilize",
    "robust solution","comprehensive overview","in today's world",
    "as we navigate","the landscape of","revolutionize","game-changer","leverage",
]


@dataclass
class EvalResult:
    section_key:        str
    overall_score:      float
    content_score:      float
    humanization_score: float
    ai_signature_score: float
    tone_score:         float
    structure_score:    float
    passed:             bool
    feedback:           str
    flagged_phrases:    list[str]


def evaluate_section(section: DraftedSection, mode: OutputModeConfig, api_key: str = "") -> EvalResult:
    flagged   = [p for p in AI_SIGNATURE_PHRASES if p in section.content.lower()]
    local_ai  = max(0.0, 1.0 - len(flagged) * 0.15)

    prompt = textwrap.dedent(f"""
        You are a strict editorial judge evaluating a {mode.display_name} section.
        Score each dimension 0.0–1.0 (one decimal place).

        Section: {section.title}
        Required tone: {mode.tone_profile}
        Word target: {mode.target_words_per_section} | Actual: {section.word_count}

        Content:
        ---
        {section.content[:3000]}
        ---

        Score these:
        1. content_score: depth, accuracy, evidence-backed claims
        2. humanization_score: varied sentence length, specific details, genuine voice,
           natural transitions. Penalise uniform rhythm and generic filler.
        3. tone_score: matches required tone ({mode.tone_profile})
        4. structure_score: paragraph variety, flow, clean ending

        Return ONLY valid JSON:
        {{"content_score": 0.0, "humanization_score": 0.0,
          "tone_score": 0.0, "structure_score": 0.0,
          "feedback": "3-5 specific bullet points on what to improve"}}
    """)

    try:
        data = generate_json(prompt)
    except Exception as e:
        print(f"[evaluator] scoring failed ({e}), using defaults")
        data = {"content_score": 0.7, "humanization_score": 0.7,
                "tone_score": 0.7, "structure_score": 0.7,
                "feedback": "Evaluation unavailable — proceeding."}

    cs = float(data.get("content_score",      0.7))
    hs = float(data.get("humanization_score", 0.7))
    ts = float(data.get("tone_score",         0.7))
    ss = float(data.get("structure_score",    0.7))

    overall  = cs*0.25 + hs*0.30 + local_ai*0.25 + ts*0.10 + ss*0.10
    feedback = data.get("feedback", "")
    if flagged:
        feedback += "\n\nAI phrases to remove:\n" + "\n".join(f'  - "{p}"' for p in flagged)

    return EvalResult(
        section_key=section.key, overall_score=round(overall, 3),
        content_score=cs, humanization_score=hs, ai_signature_score=local_ai,
        tone_score=ts, structure_score=ss,
        passed=overall >= mode.eval_threshold,
        feedback=feedback, flagged_phrases=flagged,
    )
