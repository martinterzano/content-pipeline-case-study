"""
orchestrator_tick.py — anonymised excerpt of the state-machine driver.

A single `tick()` reads the Asana project state, selects the first task that is
ready to advance according to the pipeline's state machine, calls the right
agent, writes outputs to disk, moves the Asana task to the next section, and
logs the result. The loop is intentionally one task per tick so that failures
are isolated and recoverable.

The full orchestrator in production handles email notifications, retry
backoff, multiple parallel tasks per tick, and a batch mode for the thesis
gate. Those are omitted here. The point of this snippet is the structure of
the state transition, not a drop-in utility.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


logger = logging.getLogger(__name__)


# Section names in Asana. The section ids are resolved at runtime by the
# AsanaClient from the project configuration.
SECTIONS = {
    "inventory": "Inventario",
    "theses_proposed": "Tesis propuestas",
    "writing": "En redacción",
    "reviewing": "En revisión",
    "needs_attention": "Requiere intervención",
    "ready_to_publish": "Listo para publicar",
    "published": "Publicado",
}


# State transitions. Each entry is: from_section -> (agent, to_section_on_success,
# to_section_on_needs_attention). The orchestrator is one dispatch table away
# from being a different pipeline — adding a stage means adding a row here
# and an agent function below.
TRANSITIONS: dict[str, tuple[str, str, str]] = {
    "inventory": ("explorer", "theses_proposed", "needs_attention"),
    "writing": ("writer_then_critics", "reviewing", "needs_attention"),
    "reviewing": ("titler_then_visualiser_then_derivator", "ready_to_publish", "needs_attention"),
}


@dataclass
class TaskState:
    """One Asana task plus the local artefacts for its slug."""

    gid: str
    name: str
    slug: str
    section: str
    outputs_dir: Path


def tick(
    asana_client,
    agents: dict[str, Callable[[TaskState], str]],
) -> TaskState | None:
    """
    Advance one task by one state transition. Returns the task that was moved,
    or None if nothing was ready to advance.
    """
    state = asana_client.read_project_state()

    # Find the first task whose current section has an outbound transition
    # and whose preconditions are met (the human has approved the thesis for
    # inventory items waiting on the first gate, etc.).
    for task in state.tasks:
        section_key = _section_key(task.section)
        if section_key not in TRANSITIONS:
            continue
        if not _preconditions_met(task, section_key):
            continue

        agent_name, success_section, attention_section = TRANSITIONS[section_key]
        logger.info("tick: advancing %s via %s", task.slug, agent_name)

        try:
            outcome = agents[agent_name](task)
        except Exception:
            logger.exception("tick: agent %s failed for %s", agent_name, task.slug)
            asana_client.move_task(task.gid, SECTIONS["needs_attention"])
            return task

        target = success_section if outcome == "ok" else attention_section
        asana_client.move_task(task.gid, SECTIONS[target])
        logger.info("tick: moved %s to %s", task.slug, SECTIONS[target])
        return task

    logger.info("tick: no task ready to advance")
    return None


def _section_key(section_name: str) -> str:
    """Reverse-lookup a section name to its internal key."""
    for key, name in SECTIONS.items():
        if name == section_name:
            return key
    return ""


def _preconditions_met(task: TaskState, section_key: str) -> bool:
    """
    Section-specific gating. For inventory items the thesis must be approved
    (a custom field or a label on the Asana task). For other sections the
    presence of the previous stage's output file is the gate.
    """
    if section_key == "inventory":
        return _thesis_approved_in_asana(task)
    if section_key == "writing":
        return (task.outputs_dir / "drafts" / task.slug / "v1.md").exists()
    if section_key == "reviewing":
        return _critics_passed(task)
    return False


def _thesis_approved_in_asana(task: TaskState) -> bool:
    # Placeholder. Production reads a custom field from the task.
    return False


def _critics_passed(task: TaskState) -> bool:
    # Placeholder. Production reads the critic report files written by the
    # agents and checks the final verdict.
    return False
