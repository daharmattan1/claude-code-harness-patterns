# Claude Code subagents that remember what they learned, in a memory you can check

This folder gives a Claude Code subagent notes that carry over from one run to the next. A fresh subagent forgets everything between runs, but once you let it keep notes, you need to know whether they actually help, and the agent shouldn't be the one editing them. The setup here stores those notes as short written rules in files you can open, and tracks which rules changed the agent's work. It's for anyone running agents on real work who wants to see what their agent has learned before trusting it.

In October my own writing agent said it had used its learned rules 351 times. It could point to the text a rule actually changed only 66 times, about 1 in 5. The other 285 might be real, but nobody can check them. If you can't audit and inspect it, if you haven't constrained it with code instead of probabilistic LLM logic, and if you can't wrap solid evals around it, you haven't got a true production pipeline yet.

## How it works

The agent reads its notes when it starts and hands back what it learned when it finishes. A separate Claude Code session saves that, so the agent never edits its own memory. A rule only counts as used if the agent can quote the line it changed. Rules nobody can show working get flagged, and a person decides whether to drop them.

The agent can still write files, so locking it out of its own memory folder takes a small code change to the script in [the hooks folder](../hooks/) that already watches what agents save.


## Files

| Path | What it is |
|---|---|
| [`bin/commit_return.py`](bin/commit_return.py) | Writes a specialist's returned reflection into its bundle. Refuses protected paths and an author committing its own return. |
| [`bin/retirement_gate.py`](bin/retirement_gate.py) | Flags learnings with no evidenced use in their last 20 runs, and reports utilization and three other metrics. |
| [`bin/agent_gate_resolve.py`](bin/agent_gate_resolve.py) | Checks that every agent a plan names exists, before the plan runs. |
| [`templates/bundle/`](templates/bundle/) | An empty memory bundle to copy. |
| [`examples/`](examples/) | A toy specialist, a toy reviewer, and a seeded bundle. |
| [`docs/`](docs/) | [Routing contract](docs/routing-contract.md), [bundle format](docs/bundle-format.md), [consolidation ritual](docs/consolidation-ritual.md). |

## Use it

Run these from your project root. `/path/to/this/repo` is where you downloaded this collection.

1. Copy the scripts into your project, for example as `tools/specialist-memory/`:

   ```bash
   mkdir -p tools/specialist-memory
   cp /path/to/this/repo/specialist-memory/bin/*.py tools/specialist-memory/
   ```

2. Write `.claude/agents/<name>.md` with no shell tools, load-first instructions and the return manifest. Start from [`examples/toy-specialist.md`](examples/toy-specialist.md).
3. Copy the empty bundle, then fill the founding profile and a short core-memory seed. You can delete the template's `README.md` from the copy.

   ```bash
   mkdir -p memory && cp -r /path/to/this/repo/specialist-memory/templates/bundle memory/<name>
   ```

4. After each run, the orchestrator commits the returned manifest. [`tests/fixtures/e2e_return.json`](tests/fixtures/e2e_return.json) is a complete manifest. `--committer` must differ from the manifest's `author`; if they match, the commit is refused with exit 1 and the bundle is left unchanged.

   ```bash
   python tools/specialist-memory/commit_return.py --bundle memory/<name> --manifest return.json --committer orchestrator
   ```

5. After twenty runs, read the retirement candidates and do the [consolidation pass](docs/consolidation-ritual.md):

   ```bash
   python tools/specialist-memory/retirement_gate.py --history memory/<name>/run_history.jsonl        --promotions memory/<name>/promoted.json --rules memory/<name>/learning_rules.jsonl        --retired memory/<name>/retired.json
   ```

Python 3.8 or later, standard library only. To run the tests, from the root of this repo:

```bash
pytest specialist-memory/tests
```
