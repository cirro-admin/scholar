# Adding a New Output Mode

Adding a new output mode takes ~10 lines in config/modes.py.

## Steps

1. Open config/modes.py
2. Add a new entry to the MODES dict:

```python
"grant_proposal": OutputModeConfig(
    name="grant_proposal",
    structure_template=["executive_summary", "background", "objectives",
                        "methodology", "budget_justification", "impact"],
    citation_style="APA",
    depth_level="deep",
    tone_profile="formal_persuasive",
    output_format="docx",
    section_prompts={
        "executive_summary": "Write a compelling 1-page summary...",
        "objectives": "State 3-5 measurable objectives in SMART format...",
    },
    max_research_rounds=4,
    eval_threshold=0.82,
),
```

3. Run: python main.py --topic "your topic" --mode grant_proposal

No other files need changing.
