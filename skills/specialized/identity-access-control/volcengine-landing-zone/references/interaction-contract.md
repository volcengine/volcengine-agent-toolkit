# Interaction Contract

This file defines only the outward communication style and result output format for `volcengine-landing-zone`.

> Hard requirements such as execution pauses, solution confirmation, phase confirmation, and file pauses are defined centrally in the `Hard Gates` section of `../SKILL.md` (G1-G6). They are not restated here.

## Outward Communication Principles

- Use task language that the user can understand. Do not proactively expose directory names, phase numbers, payload layering, `terraform output`, or internal orchestration details.
- Do not paste raw commands, temporary scripts, or parameter trial-and-error into user-facing messages, especially anything that contains credential handling or environment-variable injection.
- By default, show only the conclusions, impact, and next step that the user cares about. Do not expand internal troubleshooting details.
- In identity and logging scenarios, prioritize showing login entry points, usernames, permission explanations, and blockers. Do not default to exposing internal IDs.
- Sensitive information such as initial passwords must not be sent directly in chat. Write it into a new local file and then handle it under G4 by opening or delivering the file and prompting the user to review it.
- During solution confirmation, prefer the original document itself. Unless the user explicitly asks for a summary, do not start with a long overview.

## Communication Rhythm (Soft Constraint)

- Collect variables gradually by phase. Ask follow-up questions only when the current step truly lacks the minimum required input.
- Mechanical steps such as preflight, workspace preparation, blueprint sync, and plan generation should run in the background by default. Mention them explicitly only when something is blocked, when a milestone is reached, or before a write action.
- Any pause, confirmation, or file-open step is governed by G2 or G4. This file does not redefine them.
- If tasklists or checklists are used, refer to them outwardly as the "current execution steps" or the "current progress". Do not overwhelm the user with deeply nested lists.

## Result Summary Format

Every result summary must include:

- `Execution Goal`
- `Succeeded`
- `Failed`
- `Manual Follow-up`
- `Recommended Next Step`

Generic success template:

- Execution Goal: `<goal of this phase>`
- Succeeded: `<confirmed completed results>`
- Failed: `None`
- Manual Follow-up: `None`
- Recommended Next Step: `<continue to the next phase or request a user confirmation action>`

Generic partial-success template:

- Execution Goal: `<goal of this phase>`
- Succeeded: `<confirmed completed results>`
- Failed: `<the real current blocker>`
- Manual Follow-up: `<items that only need completion, not a full restart>`
- Recommended Next Step: `<reconcile first / fix the prerequisite / then decide whether to continue>`

Generic waiting-for-confirmation template:

- Execution Goal: `<goal that is prepared and ready to execute>`
- Succeeded: `<preparation work that is already done>`
- Failed: `None`
- Manual Follow-up: `<real write actions still waiting for user confirmation>`
- Recommended Next Step: `<describe the pending action and wait for confirmation>`

Usage notes:

- Phase-specific result examples should be maintained in the corresponding phase document or guidebook whenever possible.
- The `landing-zone-setup` summary report must always use `./skills/volcengine-landing-zone/assets/html/landing-zone-setup-report-template.html` and output to `./volcengine-landing-zone-workspace/outputs/landing-zone-setup-report.html`.
- Keep the summary report concise. At minimum it should contain per-phase execution details, key delivered files, manual follow-up items, and recommended next steps.
- After the report is produced, handle it under G4 by opening or delivering it first, then asking the user to review it.
