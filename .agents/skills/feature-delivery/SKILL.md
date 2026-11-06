---
name: feature-delivery
description: Deliver substantial Nightjar features from a repository specification through implementation, independent review, verification, and human integration approval.
---

Read AGENTS.md, NEXT.md, and the active spec. Use docs/WORKFLOW.md for role selection,
handoffs, approval boundaries, and the report format. Inspect affected implementation
and tests before planning. For trivial edits, use the short path in that workflow.

State explicit acceptance criteria and definition of done before implementation
(a short checklist for small tasks), then map them to a small file plan. Resolve material specification ambiguity
before dependent implementation. Ask architecture to analyze high-risk interfaces;
parallelize only independent analysis or disjoint file ownership. Give implementation
agents a bounded slice, owned files, and required tests.

After implementation, run targeted checks and the full gates. Request a fresh-context
review of the actual diff; simulation changes also need simulation review and QA.
Automatically resolve blocking findings and revalidate affected behavior within the
approved scope; routine edits/checks and bounded delegation need no repeated approval.
Use the enforced read-only review route in docs/WORKFLOW.md when supported; do not
describe instruction-only native reviewers as sandbox-isolated. Record actual role/task
identifiers, corrections, commands, acceptance evidence, and remaining risks in the
task report. Prepare the complete reviewable result before requesting integration
approval. Never treat completion of checks as approval to commit, push, or merge.

Stop when acceptance and definition of done are met, human intervention is needed,
or further changes exceed scope. Report the concrete blocker or decision. Dependencies,
significant architecture changes, destructive actions and external writes require
human authorization before execution. Do not start the next milestone automatically.
Read-only next-milestone planning may be delegated provisionally during this task;
reconcile it with the final integrated code before requesting authorization to execute.
