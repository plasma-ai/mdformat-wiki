# AGENTS

This file provides guidance to coding agents (Claude Code, Codex) when
working with code in this repository. If you are not Claude Code (which
already reads parent directories), also check the parent directory for
`AGENTS.md`.

## Overview

`mdformat-wiki` is an [mdformat](https://mdformat.readthedocs.io)
parser-extension plugin built for wikis maintained by
[plasma-wiki](https://github.com/plasma-ai/wiki).

This plugin keeps wiki page faces byte-stable: `[[...]]` wikilinks parse
atomically (never escaped, and wrap-atomic under `--wrap` -- the whole
face moves between lines as one unit, like an inline code span),
frontmatter renders byte-verbatim, and the index delimiter (written
exactly as `***`) keeps its face while every other break style delegates
to mdformat's default renderer.

The `mdformat_wiki` package holds its logic in `plugin.py` —
`update_mdit()` registers the parse rules and `RENDERERS` overrides
rendering, wildcard re-exported from `__init__.py` — with the pytest
suite in `tests/` asserting byte-identical, idempotent round-trips over
the static corpora in `tests/fixtures/`.

## Build & Development

```bash
# install dev dependencies (creates a .venv if none is active)
./install.sh --all-extras --groups=test,lint,type

# or set up the environment manually
uv sync --all-extras --group test --group lint --group type
uv run pre-commit install

# run tests
uv run --no-sync pytest

# run pre-commit
uv run --no-sync pre-commit run [--all-files]
```

The test suite uses `pytest` with `--doctest-modules` enabled.
