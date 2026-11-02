# Routing contract: how work reaches a specialist

A persistent specialist only learns if work actually goes through it. If a domain's work is
sometimes done by the specialist and sometimes by whatever agent is in front of the user,
the specialist's memory sees half the runs and its retirement numbers mean nothing. So the
contract is about routing first and memory second.

## Two ways in, one core

1. **Plan mode.** A plan phase carries `**Agent Gate:** <type>`. The executor spawns that
   subagent type for the phase. `bin/agent_gate_resolve.py` checks before the run that every
   gate names an agent that exists.
2. **Interactive mode.** The skill or instruction that owns the domain says to route the work
   to the specialist. The main agent spawns it and acts as the orchestrator.

Both run the same four steps. Only the identity of the orchestrator differs.

## The four steps

1. **Route and spawn.** The orchestrator spawns `<type>` with the task.
2. **Load on spawn.** The specialist's first action is reading its bundle: founding profile,
   core memory, learning rules. This is what makes it persistent rather than a fresh subagent
   with a long prompt.
3. **Reflect on return.** The specialist does the work, writing only under `_workspace/`, and
   ends with a manifest: a first-person evolution entry, any new rules, which rules fired
   (each with the output text it shaped), what it missed. It writes nothing else.
4. **Commit on return.** The orchestrator saves the manifest and runs
   `bin/commit_return.py --bundle memory/<type> --manifest <file>`. A different principal
   commits than authored.

## Why the specialist cannot commit its own memory

- **The wall:** its tool list has no shell, so it cannot run `commit_return.py`. This is
  structural; the harness enforces a subagent's tool list.
- **The check:** `commit_return.py` refuses a manifest whose author equals the committer. That
  catches a mistake (an orchestrator passing the wrong name). It is not a wall: a script cannot
  see who called it.
- **The gap:** the specialist has `Write`, and nothing in the tool list stops it writing a
  bundle file directly. Its prompt forbids it. If that matters to you, add the bundle paths to
  a write gate (see the hooks folder) for the specialist's agent type.

## Adding a specialist

1. Write `.claude/agents/<name>.md` (see `examples/toy-specialist.md`): tools without a shell,
   load-first instructions, the return manifest.
2. Copy `templates/bundle/` to `memory/<name>/`; fill the founding profile and a short core
   memory seed.
3. Route the domain's work to it: an Agent Gate in plans, a routing line in the domain skill.
4. After twenty runs, run `bin/retirement_gate.py` on its history and its rules.
