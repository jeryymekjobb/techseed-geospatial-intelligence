# Agent Instructions

## Ambiguous Instructions

- Do not silently choose between materially different interpretations. State the plausible options and ask for direction before consequential work.
- Read `CONTEXT.md` and `README.md` before making repository changes.

## Project Rules

- Treat this as professional Techseed work and preserve the applicable confidentiality boundary.
- Do not add customer-confidential information, personal data, credentials, secrets, or unapproved third-party data to the repository.
- Keep user-provided concepts, verified facts, assumptions, design decisions, and open questions distinguishable.
- Mark simulated, synthetic, or illustrative scenario data clearly; do not present it as live operational data.
- Do not invent data rights, sensor capabilities, satellite observations, model performance, customer commitments, or validated outcomes.
- Keep source attribution, timestamps, coordinate/reference assumptions, and data limitations explicit when they matter to a design or claim.
- Treat regulatory or safety interpretations as unresolved until checked against applicable authoritative sources and qualified review; do not present them as compliance advice.
- Prefer small, reviewable changes and keep documentation factual.

## Scope and Git Gates

- State the exact plan and scope and obtain GO before repository edits.
- A GO authorizes only its stated action and scope.
- Before staging, show the intended staged scope and proposed commit message and obtain separate GO.
- Inspect staged changes and obtain separate GO before committing.
- Push only after explicit user instruction or GO for that push.
- Run `git diff --check` before staging or committing.
- Keep each commit to one logical change.

## Wait-State Gate

Before ending a response that waits for user input, state the exact proposed action and scope, what GO permits, what NO-GO prevents, and ask for exactly GO or NO-GO.

**Vad ska göras:** `<exakt åtgärd och scope>`
**GO/NO-GO, eller beskriv vad du vill ändra.**
