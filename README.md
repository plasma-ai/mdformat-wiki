# mdformat_wiki

[![build](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/build.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/build.yaml)
[![docs](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/docs.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/docs.yaml)
[![lint](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/lint.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/lint.yaml)
[![tests](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/tests.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/tests.yaml)
[![codecov](https://codecov.io/gh/plasma-ai/mdformat-wiki/branch/main/graph/badge.svg?token=hOhrWzJqNu)](https://codecov.io/gh/plasma-ai/mdformat-wiki)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Mdformat plugin preserving wikilinks, frontmatter, and index delimiter.

---

**Source**: [https://github.com/plasma-ai/mdformat-wiki](https://github.com/plasma-ai/mdformat-wiki)

**Package**: [https://pypi.org/project/mdformat-wiki/](https://pypi.org/project/mdformat-wiki/)

---

## Installation

Install the `mdformat_wiki` package from PyPI:

```bash
pip install mdformat-wiki
```

Use `pipx install mdformat-wiki` or
`uv tool install mdformat-wiki` to install
in an isolated environment.

### Skill

Install the `/mdformat_wiki` skill for your agent via the
plugin marketplace (Claude Code and Codex):

```bash
# Claude Code
/plugin marketplace add plasma-ai/plugins
/plugin install mdformat_wiki@plasma

# Codex
codex plugin marketplace add plasma-ai/plugins
codex plugin add mdformat_wiki@plasma
```

Or from the CLI, which copies the skill into `~/.claude/skills` and
`~/.agents/skills` (add `--project` for the current project only):

```bash
mdformat_wiki install
```

## Usage

Basic usage:

```python
import mdformat_wiki
```

## Development

### Install

Run `install.sh` in the package root. With no environment active it
creates and uses a local `.venv`; with one active (e.g. pyenv) it
installs into that environment (editable), without recreating it:

```bash
./install.sh --all-extras --groups=test,lint,type
```

Run `./install.sh --help` for all options. Alternatively, run
`uv sync --all-extras --group test --group lint --group type` and
`uv run pre-commit install` to set up the environment manually.

Installing a dependency as editable (e.g. a sibling package) is left to
the caller: `uv pip install --editable <path>`.

Once installed, run tools with `uv run <command>`, or activate the
environment first (`source .venv/bin/activate`).

### Tests

Run the test suite:

```bash
pytest .
```

### Linting

Run linters and formatters:

```bash
pre-commit run --all-files
```
