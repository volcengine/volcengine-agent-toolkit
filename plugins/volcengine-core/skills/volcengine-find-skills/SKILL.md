---
name: volcengine-find-skills
description: >-
  List, select, and install Volcengine skills from the volcengine-skills marketplace. Use when a
  user asks which Volcengine skill or plugin handles a task, wants to browse every available skill,
  needs an optional skill that is not currently installed, or asks to install or check the
  installation status of a Volcengine skill. Also use to discover any core skill,
  including this finder. Use as a fallback during a Volcengine operation when the currently loaded
  or installed skills cannot cover the required product, tool, or workflow; inspect the full
  catalog, select the missing capability, and install it.
license: MIT
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - npx
---

# Volcengine Skills Finder

Use the bundled catalog to inspect every available skill and select the minimum skill set that
covers the request. Treat plugin ownership as catalog classification only; install exact skills.

## Decision flow

1. Detect whether the request starts with skill discovery or whether an active Volcengine task has
   reached a capability gap in the currently loaded or installed skills.
2. Preserve completed work and pause only the unsupported part of the active task.
3. List the complete catalog without changing installation state.
4. Inspect every name, product domain, summary, and keyword, then select the minimum exact skill set
   that covers the user's request. Make the selection directly when the catalog provides enough
   information.
5. Pass only exact skill names to the installer. Use plugin ownership to explain classification,
   never as the installation target.
6. Install through the `skills` CLI and verify the resulting installed state. Never report success
   from process exit alone.
7. If the host cannot load a newly installed skill into the current thread, tell the user to start
   a new thread and restate the original task plus completed context.

## List and select skills

Run the script relative to this skill directory:

```bash
python3 scripts/find_skills.py list
python3 scripts/find_skills.py list --json
python3 scripts/find_skills.py info <skill-or-plugin>
```

Always read the complete `list` output before selecting a skill. Use `--json` when keywords or the
English summaries help distinguish related skills. Choose by responsibility rather than name alone;
install multiple skills only when the request crosses distinct responsibilities.

The catalog includes all four skills in `skills/core/` and every optional skill owned directly by a
product-domain plugin. `skills/specialized/<domain>/<skill>/` contains generated copies of those
optional skills, grouped by the plugin name without `volcengine-`; each skill is listed only once
in the catalog. If none of the listed responsibilities covers the request, report that the
repository does not currently provide a matching skill.

## Recover from a capability gap

Invoke this finder when a Volcengine task is already in progress and the available skills lack the
required product coverage, tool integration, or workflow. Treat that gap as a discovery request:
list the complete catalog, select and install the matching skill, then continue when the host can
load it. Carry forward the original goal, relevant evidence, and completed work so discovery does
not restart the task from scratch.

## Install selected skills

Install one or more exact skills for the current host:

```bash
python3 scripts/find_skills.py install <skill> [<skill> ...] --agent <agent-name>
python3 scripts/find_skills.py install volcengine-iac --agent codex
```

The script uses `npx skills add --skill` with `--full-depth` to discover skills nested under product
categories and plugin directories. It accepts only exact skill names, installs those skills directly, and verifies
every selected name with `skills list`. Omit `--agent` only when host auto-detection is intended.
Passing a plugin name is an error, even when every skill in that plugin is needed.

Use `--scope global` for user-level installation or `--scope project` for the current project. The
default is global. `--source` may point at a reviewed local checkout or another repository source;
otherwise the catalog's official repository is used.

Use `--dry-run` when the user asks to inspect the command first. Installation is local, but any
later cloud-resource operation remains governed by the installed skill's own confirmation and
safety rules.

## Check status

Inspect catalogued skill installation state for the current host:

```bash
python3 scripts/find_skills.py status --agent codex
```

Do not equate "skill installed" with "skill loaded in this thread". Use the status only to verify
installation; start a new thread when the host cannot dynamically load the newly installed skill.
