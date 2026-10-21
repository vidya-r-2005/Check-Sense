# CheckSense agent rules (binding)
- Read docs/MASTER_SPEC.md first. Work phase by phase; stop at each checkpoint and wait for approval.
- REAL DATA ONLY. Never fabricate datasets, labels or metric values. If blocked, write steps to docs/HUMAN_TODO.md and stop that branch.
- Verify every download (metadata, checksum, licence) and record it in data/MANIFEST.md.
- Gold labels need label_status=verified (human-confirmed). LLM drafts stay "draft". Evaluation refuses non-verified rows.
- Reports and README numbers come from logged runs in results/ (config, seed, git commit stored beside them).
- Windows + VS Code friendly: pathlib, no bash-only commands, one CLI: python -m checksense.cli <command>.
- Python 3.11+, src layout, type hints, pytest, ruff, pinned dependencies, fixed seeds.
- Do not commit data/raw, models, .env or keys. Confirm before running destructive terminal commands.
- Mark every module in README as working / untested on real data / todo. Be honest about status.
