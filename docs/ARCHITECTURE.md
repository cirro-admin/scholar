# Architecture Deep-Dive

## Core design principle
One pipeline, many output modes. The OutputModeConfig dataclass in
config/modes.py is the only thing that changes between a PhD thesis and a
blog post. Everything else is identical.

## Two HITL checkpoints
1. Checkpoint 1 (query approval): After query generation, before crawling.
2. Checkpoint 2 (outline approval): After synthesis, before full drafting.

## Research agent — ReAct loop
1. Generate queries from topic + mode context
2. [HITL] User approves/edits queries
3. Dispatch to all enabled sources in parallel
4. Reflect — generate follow-up queries if gaps exist
5. Stop when coverage sufficient or max rounds reached
6. Synthesize into structured notes by topic cluster

## Writing workflow — LangGraph graph
Nodes: outline_gen → hitl_outline → section_draft → evaluate → format
The evaluate node loops back to section_draft if score < threshold.
