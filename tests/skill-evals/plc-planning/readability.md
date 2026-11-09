# Readability grader

Run the case checker before grading. Inspect the generated Markdown and the
agent's actual tool transcript. Report pass/fail with a location for each
failed item; do not infer skill use from the agent's final claim.

1. Scope, next steps, acceptance, results and limitations are easy to locate
   when applicable. Inapplicable sections, placeholders and copied authoring
   instructions are absent. A new plan has no invented execution evidence.
2. Explanations use short connected prose; distinct topics have headings;
   sequences use ordered steps. Comparisons and repeated short records use
   tables when they improve scanning. Long narratives are not squeezed into
   table cells. Do not grade by a quota of headings, bullets or diagrams.
3. Behavior, design and delivery each have one authoritative home. The design
   comparison explains the choice and reader/reload failure flow. Each
   requirement has an observable result and a concrete proving check.
4. In growing-evidence, both prior and new source revisions, counts, methods,
   expectations, dates, environment and browser limitations remain available.
   Required unrun checks stay pending; state does not claim verification.
5. Inspect tool use to identify the skill actually loaded. Planning, checkpoint
   and wrapup trials test implicit selection. Execution trials explicitly invoke
   the supported execution skill or wrapper and authorize only fixture work.

For execution-progress and wrapup variants of growing-evidence, use separate
fresh fixtures. Replace the checkpoint request with an explicit execution
invocation authorizing only reconciliation of the supplied results, or with
"Wrap up this session; reconcile the supplied results from receipts.md into
the reload PLC's evidence section, leaving receipts.md unchanged. Leave unmet
acceptance open. Do not merge or push." Keep all other facts and constraints unchanged.

Record host/model, skill revision, prompt, actual selected skills, checker
result, rubric verdict and limits. Compare baseline and revised trials using
the same fixtures and rubric. Missing host trials are missing acceptance.
