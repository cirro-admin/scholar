"""
writing_workflow/evaluator.py
──────────────────────────────
LLM judge + quality scorer for the eval-optimizer loop.

Scores each drafted section on 5 dimensions:
  1. Content quality    — accuracy, depth, use of sources
  2. Humanization       — does it read like a real person wrote it?
  3. AI-signature check — does it contain detectable AI patterns?
  4. Tone match         — matches the mode's required tone profile
  5. Structure          — appropriate length, paragraph variety, flow

Overall score = weighted average. If below eval_threshold, returns
specific actionable feedback for the re-draft.
"""

from __future__ import annotations
import os, json, textwrap
from dataclasses import dataclass
import google.generativeai as genai

from config.modes import OutputModeConfig
from writing_workflow.section_drafter import DraftedSection


# AI signature phrases — presence of these lowers the humanization score
AI_SIGNATURE_PHRASES = [
    "in today's rapidly evolving",
    "it is worth noting",
    "it's important to note",
    "in the realm of",
    "delve into",
    "multifaceted",
    "it is clear that",
    "in conclusion, this",
    "overall, it is",
    "straightforward",
    "leverage",  # as verb
    "utilize",
    "robust solution",
    "comprehensive overview",
    "in today's world",
    "as we navigate",
    "the landscape of",
    "revolutionize",
    "game-changer",
]


@dataclass
class EvalResult:
    section_key:       str
    overall_score:     float        # 0.0 – 1.0
    content_score:     float
    humanization_score: float
    ai_signature_score: float       # 1.0 = no AI patterns, 0.0 = full of them
    tone_score:        float
    structure_score:   float
    passed:            bool
    feedback:          str          # specific re-draft instructions if failed
    flagged_phrases:   list[str]    # specific AI phrases found


def _count_ai_phrases(text: str) -> list[str]:
    lower = text.lower()
    return [p for p in AI_SIGNATURE_PHRASES if p in lower]


def evaluate_section(
    section: DraftedSection,
    mode: OutputModeConfig,
    api_key: str = "",
) -> EvalResult:
    """Score a drafted section and return structured feedback."""
    key = api_key or os.getenv("GOOGLE_API_KEY", "")
    genai.configure(api_key=key)

    # Fast local check for AI phrases
    flagged = _count_ai_phrases(section.content)
    local_ai_score = max(0.0, 1.0 - (len(flagged) * 0.15))

    model  = genai.GenerativeModel("gemini-1.5-flash")
    prompt = textwrap.dedent(f"""
        You are a strict editorial judge evaluating a section of a {mode.display_name}.
        Score each dimension from 0.0 to 1.0 with one decimal place.

        SECTION TITLE: {section.title}
        REQUIRED TONE: {mode.tone_profile}
        WORD TARGET: {mode.target_words_per_section}
        ACTUAL WORD COUNT: {section.word_count}

        CONTENT TO EVALUATE:
        ---
        {section.content[:3000]}
        ---

        Score these dimensions:

        1. content_score: Does it cover the topic with depth and accuracy?
           Penalise vague generalities and reward specific claims backed by evidence.

        2. humanization_score: Does it read like a real expert wrote it?
           Reward: varied sentence length, specific details, natural transitions,
           genuine voice, appropriate hedging, real examples.
           Penalise: uniform sentence rhythm, filler phrases, generic claims.

        3. tone_score: Does it match the required tone ({mode.tone_profile})?
           Penalise mismatches (e.g. casual language in academic mode).

        4. structure_score: Is the paragraph variety good? Does it flow?
           Penalise: walls of uniform text, abrupt endings, missing transitions.

        Return ONLY valid JSON, no markdown fences:
        {{
          "content_score": 0.0,
          "humanization_score": 0.0,
          "tone_score": 0.0,
          "structure_score": 0.0,
          "feedback": "Specific, actionable re-draft instructions in 3-5 bullet points.
                       Start each bullet with the exact change needed."
        }}
    """)

    try:
        raw  = model.generate_content(prompt).text.strip()
        data = json.loads(raw)
    except Exception as e:
        print(f"[evaluator] LLM scoring failed ({e}), using defaults")
        data = {
            "content_score": 0.7,
            "humanization_score": 0.7,
            "tone_score": 0.7,
            "structure_score": 0.7,
            "feedback": "LLM evaluation unavailable — proceeding with draft as-is.",
        }

    content_score      = float(data.get("content_score",      0.7))
    humanization_score = float(data.get("humanization_score", 0.7))
    tone_score         = float(data.get("tone_score",         0.7))
    structure_score    = float(data.get("structure_score",    0.7))
    ai_signature_score = local_ai_score  # use local check — faster + more reliable

    # Weighted average: humanization + AI check weighted highest
    overall = (
        content_score      * 0.25 +
        humanization_score * 0.30 +
        ai_signature_score * 0.25 +
        tone_score         * 0.10 +
        structure_score    * 0.10
    )

    # Build feedback with AI phrase callouts
    feedback = data.get("feedback", "")
    if flagged:
        feedback += (
            f"\n\nAI SIGNATURE PHRASES DETECTED — remove or rephrase these:\n" +
            "\n".join(f'  - "{p}"' for p in flagged)
        )

    return EvalResult(
        section_key=section.key,
        overall_score=round(overall, 3),
        content_score=content_score,
        humanization_score=humanization_score,
        ai_signature_score=ai_signature_score,
        tone_score=tone_score,
        structure_score=structure_score,
        passed=overall >= mode.eval_threshold,
        feedback=feedback,
        flagged_phrases=flagged,
    )
