# A plan file an agent can pick up after it forgets everything

A spec and templates for long Claude Code tasks that outlive a context window, plus a skill that has two other models review a plan before it runs.

## Files

| Path | What it is |
|---|---|
| [SPEC.md](SPEC.md) | The plan-file spec: state section, one action per iteration, the IN FLIGHT rule, gate classes, escape hatches, sizing. |
| [templates/prd_full.md](templates/prd_full.md) | A full plan file for 8 or more phases. |
| [templates/prd_lite.md](templates/prd_lite.md) | A lite plan file for 3 to 7 phases. |
| [templates/exemplars/](templates/exemplars/) | Two pattern cards showing what a good plan looks like in one category: signals, parameters, criteria that worked, a phase skeleton, failure modes. |
| [skills/cross-model-review/](skills/cross-model-review/) | A Claude Code skill that sends a plan to Codex and Gemini on four lenses, tests each finding, and returns REVISE, INCOMPLETE or APPROVED. |

## Use it

1. Copy a template into your project's plans folder and fill every bracket. SPEC.md says what each field is for.
2. Before a plan of 10 or more phases runs, review it: copy `skills/cross-model-review/` into `.claude/skills/` and run `bash .claude/skills/cross-model-review/scripts/run_review.sh <plan.md> <out-dir>`. It needs bash, `timeout` (coreutils on macOS) and the Codex and Gemini CLIs; set the model names in the script's config block.
3. Run the plan one action per iteration with whatever runner you use. The runner, planner and scoring skills I use come in v1.1.

Before a plan gets written, I have the agent interview me one question at a time. That step is adapted from Matt Pocock's grill-me skill in [mattpocock/skills](https://github.com/mattpocock/skills), so it isn't repackaged here.
