"""
writing_workflow/orchestrator.py
──────────────────────────────────
LangGraph writing workflow graph.

Graph nodes:
  generate_outline  →  [HITL: approve outline]  →  draft_sections
  →  evaluate_sections  →  (loop back if failed)  →  format_output

State is a TypedDict passed through every node.
"""

from __future__ import annotations
import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from config.modes import OutputModeConfig
from research_agent.synthesizer import ResearchBundle
from writing_workflow.outline_gen import Outline, SectionPlan, generate_outline
from writing_workflow.section_drafter import DraftedSection, draft_section
from writing_workflow.evaluator import EvalResult, evaluate_section
from writing_workflow.formatter import FormattedOutput, render


# ── Graph state ───────────────────────────────────────────────────────────────

class WritingState(TypedDict):
    bundle:          ResearchBundle
    mode:            OutputModeConfig
    api_key:         str
    output_dir:      str

    outline:         Outline | None
    sections:        list[DraftedSection]
    eval_results:    list[EvalResult]
    failed_sections: list[str]          # keys of sections needing re-draft
    draft_iterations: dict[str, int]    # key → number of drafts attempted
    context_so_far:  str                # accumulated text for consistency

    final_output:    FormattedOutput | None
    hitl_outline_approved: bool


# ── Nodes ─────────────────────────────────────────────────────────────────────

def node_generate_outline(state: WritingState) -> dict:
    print("[orchestrator] Generating outline...")
    outline = generate_outline(
        bundle=state["bundle"],
        mode=state["mode"],
        api_key=state["api_key"],
    )
    return {"outline": outline, "hitl_outline_approved": False}


def node_hitl_outline(state: WritingState) -> dict:
    """
    HITL checkpoint 2: display the outline and wait for user approval.
    In a web UI this would pause and send the outline to the frontend.
    In CLI mode it prints and prompts.
    """
    outline = state["outline"]
    print("\n" + "="*60)
    print(f"OUTLINE: {outline.title}")
    print("="*60)
    for sec in outline.sections:
        print(f"  {sec.title}")
        print(f"    {sec.brief[:100]}...")
    print("="*60)

    response = input("\nApprove outline? [y/n/edit] ").strip().lower()

    if response == "n":
        # Allow user to remove sections
        print("Enter section keys to remove (comma-separated), or press Enter to keep all:")
        to_remove = input("> ").strip()
        if to_remove:
            remove_set = {k.strip() for k in to_remove.split(",")}
            outline.sections = [s for s in outline.sections if s.key not in remove_set]
            print(f"Removed sections: {remove_set}")

    return {"outline": outline, "hitl_outline_approved": True}


def node_draft_sections(state: WritingState) -> dict:
    """Draft all sections (or re-draft failed ones)."""
    outline  = state["outline"]
    mode     = state["mode"]
    api_key  = state["api_key"]
    bundle   = state["bundle"]
    context  = state["context_so_far"]
    existing = {s.key: s for s in state["sections"]}
    iters    = dict(state["draft_iterations"])
    failed   = state["failed_sections"]

    # On first pass draft everything; on re-draft only failed sections
    to_draft = [s for s in outline.sections
                if not failed or s.key in failed]

    new_sections = dict(existing)

    # Draft abstract last so it can summarise what was actually written
    deferred  = [p for p in to_draft if p.key == "abstract"]
    immediate = [p for p in to_draft if p.key != "abstract"]

    for plan in immediate + deferred:
        iters[plan.key] = iters.get(plan.key, 0) + 1
        print(f"[orchestrator] Drafting: {plan.title} "
              f"(attempt {iters[plan.key]}/{mode.max_draft_iterations})")

        # For abstract on first attempt, inject a summary of completed sections
        extra_context = context
        if plan.key == "abstract" and new_sections:
            completed = [s for k, s in new_sections.items()
                         if k not in ("abstract", "table_of_contents", "references")]
            if completed:
                summary = "\n\n".join(
                    f"[{s.title}]\n{s.content[:400]}" for s in completed[:4]
                )
                extra_context = f"COMPLETED SECTIONS SUMMARY:\n{summary}\n\n{context}"

        drafted = draft_section(
            section=plan,
            bundle=bundle,
            mode=mode,
            context_so_far=extra_context,
            api_key=api_key,
        )
        new_sections[plan.key] = drafted
        context += f"\n\n{drafted.content}"

    ordered = [new_sections[s.key] for s in outline.sections if s.key in new_sections]

    return {
        "sections": ordered,
        "context_so_far": context,
        "draft_iterations": iters,
        "failed_sections": [],
    }


def node_evaluate_sections(state: WritingState) -> dict:
    """Evaluate all sections that haven't passed yet."""
    mode       = state["mode"]
    api_key    = state["api_key"]
    iters      = state["draft_iterations"]
    existing_evals = {e.section_key: e for e in state["eval_results"]}

    new_evals  = dict(existing_evals)
    failed     = []

    for section in state["sections"]:
        # Skip if already passed
        prev = existing_evals.get(section.key)
        if prev and prev.passed:
            continue

        result = evaluate_section(section, mode, api_key)
        new_evals[section.key] = result

        if not result.passed:
            attempts = iters.get(section.key, 1)
            if attempts < mode.max_draft_iterations:
                failed.append(section.key)
                print(f"[orchestrator] {section.key}: score={result.overall_score:.2f} "
                      f"— re-drafting (attempt {attempts+1}/{mode.max_draft_iterations})")
            else:
                print(f"[orchestrator] {section.key}: score={result.overall_score:.2f} "
                      f"— max attempts reached, accepting best draft")
        else:
            print(f"[orchestrator] {section.key}: score={result.overall_score:.2f} — passed")

    return {
        "eval_results": list(new_evals.values()),
        "failed_sections": failed,
    }


def node_format_output(state: WritingState) -> dict:
    print("[orchestrator] Formatting final output...")
    output = render(
        outline=state["outline"],
        sections=state["sections"],
        mode=state["mode"],
        output_dir=state["output_dir"],
    )
    return {"final_output": output}


# ── Edges ─────────────────────────────────────────────────────────────────────

def should_redraft(state: WritingState) -> str:
    if state["failed_sections"]:
        return "draft_sections"
    return "format_output"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(WritingState)

    graph.add_node("generate_outline",   node_generate_outline)
    graph.add_node("hitl_outline",       node_hitl_outline)
    graph.add_node("draft_sections",     node_draft_sections)
    graph.add_node("evaluate_sections",  node_evaluate_sections)
    graph.add_node("format_output",      node_format_output)

    graph.set_entry_point("generate_outline")
    graph.add_edge("generate_outline",  "hitl_outline")
    graph.add_edge("hitl_outline",      "draft_sections")
    graph.add_edge("draft_sections",    "evaluate_sections")
    graph.add_conditional_edges(
        "evaluate_sections",
        should_redraft,
        {"draft_sections": "draft_sections", "format_output": "format_output"},
    )
    graph.add_edge("format_output", END)

    return graph


# ── Public interface ──────────────────────────────────────────────────────────

def run_writing_workflow(
    bundle: ResearchBundle,
    mode: OutputModeConfig,
    api_key: str = "",
    output_dir: str = "./outputs",
) -> FormattedOutput:
    """Run the full writing workflow and return the path to the final output file."""
    key   = api_key or os.getenv("GOOGLE_API_KEY", "")
    graph = build_graph().compile(checkpointer=MemorySaver())

    initial_state: WritingState = {
        "bundle":          bundle,
        "mode":            mode,
        "api_key":         key,
        "output_dir":      output_dir,
        "outline":         None,
        "sections":        [],
        "eval_results":    [],
        "failed_sections": [],
        "draft_iterations": {},
        "context_so_far":  "",
        "final_output":    None,
        "hitl_outline_approved": False,
    }

    config = {"configurable": {"thread_id": "scholar_run"}}
    final  = graph.invoke(initial_state, config)

    return final["final_output"]
