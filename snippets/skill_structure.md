# Agent Skill Structure (redacted template)

Each agent in the pipeline is a Claude Code skill: one `SKILL.md` file that is
invoked as a slash command (`/blog-explorer`, `/blog-redactor`, etc.). The
skill file is the agent's prompt plus the convention for how it reads its
corpus, writes its output, and reports its result.

This file is the structural template. The actual production skills follow this
shape with voice-specific rules filled in for each agent. The specific rules
are redacted.

---

## Role

One sentence describing the agent's single responsibility. The scope of the
agent should be a single step of the pipeline. If the role sentence requires
"and" between two separate objectives, the agent is doing two jobs and should
be split (see §6 of the case study README for an example of this reasoning).

Example (Writer): *Produce a first draft of a blog article from an approved
thesis, following the voice rubric.*

---

## Inputs

- `inputs/<slug>/thesis.md`: the approved thesis for this article.
- `knowledge_base/`: shared corpus loaded via `_default_corpus_for(agent_name)`
  in `llm_client.py`. The Writer loads: `style_rubric.md`, `wording_rules.md`,
  `target_pages.md`, the author's voice files.
- `writing_voice/learnings.md`: structured log of the author's manual edits on
  previously approved articles (see §8 of the case study README).

The convention is: no agent reads a file not listed here, and no agent writes
a file not listed under Output. Agents are isolated by file access, not by
runtime boundaries.

---

## Process

Each agent follows a numbered process. The number of steps is kept small
(two to five) and each step is independently inspectable in a Claude Code
session. If a step requires the agent to also do interpretive judgment on its
own output, that interpretation becomes a new step with its own description.

Example structure for the Writer:

1. **Read inputs.** Load the thesis, the voice rubric, and the learnings file.
2. **Plan the argument.** Produce an outline with the main argument and the
   two or three sub-arguments that support it. The outline is internal, not
   written to disk, but is enforced by the structure of step 3.
3. **Draft the body.** Write one paragraph per sub-argument. Do not open with
   meta-commentary (see K5 in the style rubric). The dek carries the thesis;
   the body enters directly into the first sub-argument.
4. **Self-check against the K catalogue.** Scan the draft for the ten
   families of prohibited patterns. Note any detected and fix inline.
5. **Write output.** Save to `outputs/drafts/<slug>/v1.md` with front matter.

---

## Output

- `outputs/drafts/<slug>/v1.md`: the draft article. The front matter is YAML
  with `slug`, `title_placeholder`, `thesis`, `author`, `created_at`.
- Return value from the agent (printed by the skill): either `OK` or a short
  JSON object with the failure reason, consumed by the orchestrator to decide
  the next transition.

---

## Rules enforced inline

The agent's prompt includes the subset of the voice rubric that is specific
to this stage. The Writer's prompt includes the K catalogue plus the L
catalogue (voice resources). The Critic's prompt includes the K catalogue
plus the operational definitions of each K family. The division is deliberate:
each agent only loads the rules it is responsible for enforcing.

---

## Why SKILL.md rather than Python

- Skills are invokable interactively in a Claude Code session, which matches
  the author's actual working mode for the writing stages.
- Skills are prompt-first; versioning the prompt in a markdown file is more
  honest about what the agent is than a Python wrapper that embeds the same
  text in a string literal.
- The orchestrator can still call a skill unattended by invoking Claude Code
  with the skill name as an argument. The split between interactive and
  unattended operation is orthogonal to the skill-vs-Python split.
