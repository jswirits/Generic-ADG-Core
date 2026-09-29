# Generic ADG Core

Generic ADG Core is the separately versioned, system-independent semantic core for Generic ADG.

The first baseline intentionally contains one bounded capability: pure Goal Discovery and explicit
initial goal approval. It models this phase sequence:

```text
SEED_GOAL -> GOAL_DISCOVERY -> PLAN_DRAFTED -> WAITING_GOAL_APPROVAL -> APPROVED
```

State values are immutable, validated, and serializable to plain mappings. Invalid transitions,
unknown serialized fields, incomplete discovery, and malformed plans fail closed. The package has no
runtime dependency beyond the Python standard library and requires Python 3.12 or newer.

This baseline does not implement Git or project-file access, Runtime journals, policy persistence,
dispatch, retries, provider/browser/GPT/Aside adapters, Skills, product loading, or later
NEXT/Human Gate/COMPLETE semantics. `APPROVED` is the terminal phase of this baseline; development
readiness is deliberately outside its scope.

## Verify

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m compileall -q src tests
python -m unittest discover -s tests -p "test_*.py" -v
```

An exact full Git commit SHA is the executable source authority. A branch name or package version alone
is not an execution pin. This baseline does not establish a release tag.

## License

Licensed under the Apache License, Version 2.0. See `LICENSE`.

