# Local File Display (DISPLAY)

This skill often needs to put a **local file** in front of the user, such as a solution confirmation HTML file, login information, an initial password file, or an HTML summary report, instead of retelling the file in chat. `SKILL.md` references this from G1, G4, STEP 0, and STEP 3.

> Core rule: **display means letting the user open the file itself, not retelling or summarizing its contents in chat.**
> In the solution-confirmation scenario especially, do not read the HTML body first and then generate a solution explanation. The correct order is: deliver the file path first, add one short guidance line and a confirmation question, then stop and wait.

## Step 1. Copy into the Writable Workspace

- Copy the file into `${WORKSPACE_ROOT}/`. For the solution confirmation document, copy it as `${WORKSPACE_ROOT}/landing-zone-solution-plan.html`. The workspace copy is the artifact you deliver.
- This keeps the read-only assets under `${SKILL_ROOT}` untouched. See G3 in `SKILL.md`.

## Step 2. Put the File in Front of the User (Open First, Then Degrade)

Use the **first option that works** in the current runtime, in this priority order:

1. **Open it (default, do this first).** If the runtime can reach the user's machine (Claude Code, Trae, and similar local clients), you **must** actually open the file, for example macOS `open <abs.html>`, Linux `xdg-open <abs.html>`, Windows `start "" <abs.html>`. Opening is the default action, not an optional convenience. After it opens, add one short guidance line.
2. **Degrade to path + Markdown guidance.** Only if opening is unavailable or fails, give the **absolute path** of the file under `${WORKSPACE_ROOT}` plus one short guidance line such as "Please open this file in a browser to review it". You may add a **section-title-only index** (table of contents) so the user can decide whether to open it. A title-only index is not a restatement of the body. Do not rewrite each section into summary paragraphs.
3. **Last-resort fallback: retell in chat.** Only when neither opening nor delivering an openable path is meaningful (for example a pure cloud runtime with no access to the user's machine and no preview), you may restate the plan in chat. When you do, **explicitly mark it as a degraded fallback** because file access was not possible. This is the lowest tier and must never be used as a shortcut when option 1 or 2 is available.

Never start any listening process (HTTP server, tunnel, `python -m http.server`, `nc -l`) to display a file. Outside the last-resort fallback, do not read the HTML body first and turn it into a chat summary; the file stays the source of truth.

## Step 3. Solution-Confirmation Response Contract

When the file is `landing-zone-solution-plan.html`, the first user-facing turn after delivery is a strict checkpoint response, not a free-form explanation.

Allowed: one line pointing the user to the file, plus one confirmation question.

Forbidden: any summary of the solution body; any explanation of phase order, account structure, finance, identity, log, or network design; any "here is the plan" rewrite.

If you mention concrete solution content from the HTML body before the user confirms, you have violated this protocol even if the file path was delivered.

## Step 4. Stop and Wait

After the file path has been delivered, **stop** and wait for the user's explicit feedback (confirm, adjust, or continue). This pause is required by G1 (solution confirmation) and G4 (file review). G2 does not override it.
