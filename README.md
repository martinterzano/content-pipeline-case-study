# Multi-Agent Content Pipeline for a Technical Blog: Case Study

> Seven-agent system that produces technical blog articles end-to-end for the author's own consulting studio, with a single human gate before publication. The pipeline tracks state in Asana, enforces a style rubric with a deterministic linter plus an LLM critic, derives LinkedIn pieces from each approved article, and opens a pull request against the website repository. The thesis of each article is set by the human; everything else is automated.

**Sector:** self-hosted, running on the author's own consulting business (dogfooding) · **Role:** sole author and operator · **Stack:** Python · Anthropic SDK with prompt caching · Claude Code skills (SKILL.md) · Asana API · SMTP · GitHub PR workflow · **Status:** in production since 2026-09, powering an active blog

The system is designed around a single operational constraint: the author will not let the model set the thesis of an article. Every other decision in the pipeline follows from that one.

---

## Contents

1. [The problem](#1-the-problem)
2. [Why a multi-agent system rather than a single prompt](#2-why-a-multi-agent-system-rather-than-a-single-prompt)
3. [Architecture overview](#3-architecture-overview)
4. [Hybrid execution: skills in Claude Code plus Python for integration](#4-hybrid-execution-skills-in-claude-code-plus-python-for-integration)
5. [The thesis is not automated](#5-the-thesis-is-not-automated)
6. [Separation of writing and titling](#6-separation-of-writing-and-titling)
7. [Two layers of style enforcement: deterministic linter plus LLM critic](#7-two-layers-of-style-enforcement-deterministic-linter-plus-llm-critic)
8. [Feedback loop without retraining](#8-feedback-loop-without-retraining)
9. [Human gates and the Asana state machine](#9-human-gates-and-the-asana-state-machine)
10. [Scoping decisions and repository contents](#10-scoping-decisions-and-repository-contents)
11. [What this case study demonstrates](#11-what-this-case-study-demonstrates)

---

## 1. The problem

A new consulting studio has to publish technical content from day one for two reasons that pull in the same direction. SEO takes months to index and rank, so starting late means paying the delay twice. And the author's LinkedIn algorithm visibility now responds to published activity, so a cold profile with no public writing underperforms even on passive search. Those two forces mean the production has to start before the business has clients to write about.

Three concrete constraints shape the production system:

- **Voice consistency across pieces.** The studio's positioning depends on a specific register (sober-direct, no AI-signature prose, no vague claims). Each article has to pass that filter without flattening into generic consulting content.
- **Explicit anti-patterns.** Certain topics are off-limits because they contradict positioning decisions already made elsewhere (no promotion of specific low-margin tools, no "trending AI topics" framing). An article that violates these turns months of positioning work into content that undoes it.
- **One operator.** The author writes, operates the business, and runs the content system. Any step that cannot be delegated to an agent has to be fast and tolerant of interruption.

The pipeline is designed to resolve these three constraints with one architectural answer: specialise each stage of production to one job, make the output of each stage inspectable, and keep the human only in the places where the human adds judgment the model cannot.

## 2. Why a multi-agent system rather than a single prompt

A single prompt that takes "write an article about X" and returns a finished piece is the baseline. It is faster to build and cheaper to run. The multi-agent decomposition is justified when three conditions hold at the same time.

**Different stages optimise for contradictory criteria.** The Writer optimises for sustaining a single thesis across 1,500 words. The Titler optimises for tension and click-through, which is sometimes at odds with faithful summarisation. The Technical Critic optimises for falsifiability and the Style Critic optimises for a specific set of pattern violations. Asking a single model to balance all four produces output that is average on each axis.

**Intermediate outputs are inspectable and reusable.** A monolithic prompt returns one artefact. A seven-stage pipeline returns seven, which means the author can replace or re-run a single stage without regenerating the rest. If the title is wrong, the fix is one Titler re-run with a different seed, not a full regeneration that may change the body.

**Failure modes compose predictably.** When the single-prompt output is wrong, the author has to diagnose the whole chain of reasoning in one shot. With specialised agents, failure is localised: the Technical Critic rejects a specific claim with a specific reason, and only the Writer re-runs. Debugging a system that fails one step at a time is tractable in a way that debugging a monolithic generator is not.

## 3. Architecture overview

Seven agents, orchestrated as a state machine with Asana as the visible state store.

| Agent | Responsibility | Output |
|---|---|---|
| Explorer | Reads the inventory, proposes 2 to 4 complementary theses per topic, each with 2 supplementary alternatives | Candidate theses, written to the Asana task |
| Writer | Takes an approved thesis and produces a draft article following the voice rubric | `drafts/{slug}/v1.md` |
| Technical Critic | Reads the draft and checks factual claims, falsifiability of promises, internal consistency | Pass or revision list |
| Style Critic | Reads the draft and checks the voice rubric (prohibited patterns, hedging caps, meta-commentary, LLM signatures) | Pass or revision list |
| Titler | Runs after Style passes. Generates 3 to 5 title and dek variants with distinct angles, scores each on five criteria, picks the highest | Final title plus dek |
| Visualiser | Decides whether the article needs a structural diagram (architecture, comparative, decision flow). If yes, produces an inline SVG with the studio's palette. Always produces a spec plus prompt for the hero image | SVG files, hero spec |
| Derivator | Takes the approved article and derives four LinkedIn pieces (long-form post, short post, carousel, poll) | `approved/{slug}/linkedin.md` |

The orchestrator moves tasks through Asana sections as agents finish their steps. The publisher reads tasks from "Ready to publish", generates the HTML, updates the sitemap, replaces the index CTA, removes `noindex` from the stub, and opens a pull request against the website's main branch. The merge is manual.

Behind the agents is a small Python layer: an LLM client with prompt caching that reads a per-agent corpus from local files, an Asana client that caches section ids for batch updates, an email notifier for the human gate, and deterministic validators (em dash counter, voseo detector, banned-terms matcher, LLM-pattern linter) that run before the LLM-based Style Critic sees the text.

## 4. Hybrid execution: skills in Claude Code plus Python for integration

Agents of writing are implemented as Claude Code skills (`SKILL.md` files invoked as slash commands like `/blog-explorer`, `/blog-redactor`, `/blog-titulador`). The orchestrator, Asana client, publisher and email notifier are Python scripts.

The split is deliberate.

Skills live inside a Claude Code session. The author can run `/blog-ciclo` and see each agent's output interactively, inspect intermediate drafts, intervene when a thesis needs refinement. The skills reuse the same corpus-loading convention that works in another repository of the author's (job-search-automation), so the pattern is already debugged.

Python handles everything that has to run outside a chat session: Asana state transitions, email notifications, HTML generation, PR opening. These are deterministic operations that benefit from exit codes, logging to a file, and the possibility of running on a schedule in the future. Mixing them into a Claude Code session would couple infrastructure to an interactive context, which is the wrong boundary.

The orchestrator can be driven by either side: an interactive session via the `/blog-ciclo` skill, or an unattended `python orchestrator.py --tick` cron. Both produce the same state transitions.

## 5. The thesis is not automated

The system has an inventory of candidate topics. The Explorer agent reads the inventory and produces thesis proposals for each topic. The author approves one thesis per article in Asana before any writing happens.

Approving the thesis is the single step the author will not delegate. The reasoning is specific to the business context:

The studio sells "AI with judgment" as its positioning for the Automation and Agents service family. A studio that lets a model choose what to argue about its own domain is making a public argument against its own positioning. The contradiction is small on any single article and compounds across the publication history. Readers notice.

Operationally, this translates into two design choices:

**The Explorer is validated by what it rejects, not by what it proposes.** Three positioning vetoes (specific low-margin tools, generic "integration" framing, trending AI topics) took weeks of iteration to establish. The Explorer loads them as part of its corpus and must flag topics that violate them. The author audits proposals mostly for whether the Explorer caught the right vetoes, not for how creative the proposals are.

**The thesis gate is batch-friendly.** In batch mode the Explorer proposes theses for N topics in one pass. The author approves all N in one Asana session before the Writer starts on any of them. Rejecting a thesis after the Writer has produced 1,500 words is wasted tokens; rejecting it before produces almost no waste. The batch gate is cheaper per article than per-article interactive flow.

The author's edits on approved articles feed back into the system via a separate mechanism (see §8). The thesis setting itself remains outside the loop.

## 6. Separation of writing and titling

A single agent asked to produce a draft and its title tends to produce a title that is a faithful summary of the argument. Faithful summaries are poor titles. The research done against boutique DS consulting sites (Elder Research, prognostica, Modal Resonance) showed a consistent pattern: titles with a qualifier (two-part structure, specific pain, falsifiable promise), not descriptive summaries.

So the Titler is a separate agent that runs after both Critics approve the draft. It generates 3 to 5 variants following distinct angles:

- Two-part title with qualifier
- Specific-question-posed-to-the-reader
- Number plus concrete pain
- Contrarian framing
- Falsifiable promise

Each variant is scored on five criteria (substitution test, falsifiability, concrete pain, qualifier presence, length within range). The Titler picks the highest-scoring variant and writes it plus a two-line dek to the article front matter. The author does not approve the title in the loop. The author edits directly in the final article file if the Titler's choice is wrong.

The design cost of this separation is one extra agent call per article. The design benefit is that the Writer's optimisation function is cleaner (sustain the thesis, not also hook the reader), and the Titler's optimisation function is explicit (tension plus falsifiability, not faithfulness to the argument). Each agent is simpler as a result.

## 7. Two layers of style enforcement: deterministic linter plus LLM critic

The Style Critic is an LLM-based agent that reads the draft against the voice rubric (around twenty rules covering tone, prohibited patterns, hedging caps, meta-commentary). An LLM critic is appropriate for the subset of rules that require interpretation (does this paragraph open with meta-commentary disguised as context? is this hedging within acceptable density given the topic's uncertainty?).

A deterministic linter runs before the LLM Style Critic. It catches:

| Violation | Why it is deterministic |
|---|---|
| Em dashes above cap | Count regex, compare to threshold |
| Voseo verb forms | Spanish second-person variant distinct from the target tuteo |
| Banned terms list | Exact substring match |
| LLM signature patterns with frequency cap (contrastive, triple enumeration, hedging chains) | Regex count, compare to K-rule cap |
| LLM signature patterns with total prohibition (artificial deepening, meta-commentary openers, generic bridges, weak periphrases) | Regex match, zero tolerance |

The deterministic linter catches the exact rules the LLM critic tends to miscount. LLMs are reliable at identifying a pattern as present, less reliable at counting its occurrences exactly. A regex is the opposite: precise count, no interpretation. The two layers are complementary rather than redundant. Each catches what the other handles poorly.

Rules that cannot be made deterministic without producing noise (K2 reformulative appositions, K9 infinitive chains, K10 sententious closes) stay in the LLM critic. The split is explicit in the code: `pipeline/validators/llm_patterns.py` for the deterministic half, the Style Critic agent prompt for the interpretive half.

## 8. Feedback loop without retraining

The author's manual edits on approved articles are recorded in `writing_voice/learnings.md` in a structured format: *what I changed, why, emergent rule*. The Writer, both Critics and the Derivator load this file as part of their corpus at every call.

The feedback loop improves agent behaviour without any model-level change. New rules emerge from the edits, land in the shared corpus, and show up in the next cycle's outputs. The alternative design (an "observer" agent that compares v1 drafts to final published versions and proposes rules) was deferred: without a volume of 8 to 10 published articles, the observer would surface noise rather than patterns. The manual learning log is cheap, immediate and auditable.

The design assumes the author will keep writing edits. A system that depends on continued human input to improve is honest about its limits. It is not making a claim that the model learns on its own. The improvement is in the corpus, not the weights.

## 9. Human gates and the Asana state machine

Asana is both the user interface and the state store. The content project has seven sections corresponding to pipeline stages:

| Section | What tasks here represent |
|---|---|
| Inventario | Candidate topics (slug, brief, target page) |
| Tesis propuestas | Explorer has written thesis candidates, waiting for human approval |
| En redacción | Writer is producing a draft |
| En revisión | Critics are reading the draft |
| Requiere intervención | A linter or critic found something that needs human review |
| Listo para publicar | Article plus LinkedIn pieces plus visuals are approved |
| Publicado | Published via PR merge |

The orchestrator moves tasks between sections as agents finish their steps. The author uses Asana as a dashboard: everything that needs attention surfaces in "Requiere intervención" or "Listo para publicar", everything in progress is visible without opening files.

The human gate is one checkpoint: the final review in "Listo para publicar" before the publisher opens the PR. An earlier mini-gate (thesis approval, §5) exists to avoid wasted writing, but the single gate for finished output is the publishing one. One gate makes the system's quality guarantee auditable: an article is approved for publication exactly if the author moved it into "Listo para publicar" and clicked merge on the PR.

The PR itself is the second lock. Vercel deploys automatically from main, so the orchestrator stops at opening the PR. Merging the PR is the author's physical action and the point of no return. A pipeline that pushes to main directly would remove that lock and introduce a class of failure (template bug ships to production) that the current design excludes by construction.

## 10. Scoping decisions and repository contents

### 10.1 Out of scope for this public write-up

- **The author's `writing_voice/` corpus.** Three files (core.md, blog_hellium.md, linkedin_martin.md) and the feedback batches encode the specific voice the system targets. Publishing them would make the voice replicable by any reader; the point of a specific voice is that it is identifiable, not generic.
- **The articles produced.** `outputs/approved/` contains the actual publications. They are visible at the author's blog. Publishing them again here adds no signal.
- **Prompts in full.** Each `SKILL.md` is an agent prompt. The structure is described in §3 and the role each agent plays is explicit. The exact text of each prompt is specific to the author's voice and vetos and is not published.
- **Business-specific knowledge files.** `content_vetoes.md`, `publicados_con_tupla.md`, `meta_temas_publicados.md`, `target_pages.md` encode the studio's internal positioning and inventory. Not public.
- **Asana project id, Anthropic key, Gmail SMTP credentials.** All in a local `.env`.

### 10.2 What is in this repository

- `README.md`, this case study.
- `snippets/orchestrator_tick.py`, the state-machine driver function, anonymised and reduced to show the control flow of a single tick.
- `snippets/llm_patterns.py`, the deterministic linter for LLM-signature patterns (§7), with the regex catalogue intact and the frequency-cap thresholds set to the actual production values.
- `snippets/skill_structure.md`, a redacted `SKILL.md` showing the structural pattern each agent follows (role, inputs, process, output format), with the specific voice rules replaced by placeholders.

The three snippets together illustrate the three load-bearing design patterns of the system (state machine, deterministic plus LLM layered quality, prompt-as-skill-file). They are not a runnable system.

## 11. What this case study demonstrates

- **A production design decision stated as a constraint, not a feature.** "The thesis is not automated" is the first and strongest design decision. Every other architectural choice follows from it or supports it. Case studies that lead with technique often omit the constraint that forced the technique.
- **Multi-agent decomposition justified against the single-prompt baseline**, with three concrete criteria (contradictory stage optimisations, inspectable intermediate outputs, localised failure modes). The alternative is explicitly compared, not assumed inferior.
- **Hybrid runtime that reflects the actual boundary.** Skills run where interactivity matters; Python runs where determinism and scheduling matter. The split is architectural, not stylistic.
- **Determinism and interpretation treated as separate quality layers.** The regex linter catches what regex is good at; the LLM critic catches what interpretation is for. The division of labour is explicit in the code, not implicit in the agent's prompt.
- **Feedback loop that is honest about its mechanism.** Improvement happens through a human-maintained corpus of edits, not through model updates. The system does not claim to learn; it claims to use what the human has taught it.
- **One human gate, one lock, one visible state machine.** The publishing checkpoint plus the PR merge plus the Asana sections together produce a system whose quality guarantee is auditable: an article shipped exactly if the author approved it twice (section move plus merge).

---

Martín Terzano · [helliumlab.com](https://helliumlab.com) · [LinkedIn](https://www.linkedin.com/in/martinterzano) · martin@helliumlab.com
