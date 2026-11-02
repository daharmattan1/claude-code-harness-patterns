# Claude Code patterns for checking an agent's work

I run a lot of AI coding agents at once, and they're confident about their own work in a way that isn't earned. One graded its own essays 84 to 89 out of 100, and a real review gave them 71. It's convinced it's great, but it doesn't even know what great is half the time.

So I stopped trusting what agents say about their work and started checking it with plain code instead. This repo is that code: small pieces for Claude Code that check an agent's work from the outside, keep many sessions from wrecking each other, and give agents a memory you can actually audit.

## What's in here

- **[hooks/](hooks/)** checks an agent's work before it ships. The agent that writes a draft can't run commands, so a different step publishes it, and that step can hold back a long draft nobody else has reviewed.
- **[multi-terminal-git/](multi-terminal-git/)** stops many sessions on one branch from wiping out each other's work. In March 2026 one session switched branches and I lost fourteen phases of a newsletter rebuild, so now a hook blocks branch switching.
- **[specialist-memory/](specialist-memory/)** gives a subagent a memory you can check. A lesson only counts as used if the subagent can quote the work it shaped. In October mine claimed it had used its lessons 351 times and could show me 66.
- **[prd-loop/](prd-loop/)** is a plan file an agent can pick back up after it forgets everything. It comes with templates and a review step that sends a big plan to two other AI models before it runs.

## What it won't catch

The git checks block by default, but the two publishing checks in hooks/ only log a warning until you turn them on, and I still run mine that way. The hooks, git and memory pages each say what still gets past.

## Requirements and license

You need Claude Code and Python 3.8+ (pytest to run the tests). The git folder also needs git 2.40+ and bash 4.4+, and the plan review needs the Codex and Gemini command-line tools.

Code is MIT ([LICENSE](LICENSE)) and docs are CC BY 4.0 ([LICENSE-docs](LICENSE-docs)).

---

Built by Victor Sowers.
