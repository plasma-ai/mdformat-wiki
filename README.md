# mdformat-wiki

[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![build](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/build.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/build.yaml)
[![lint](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/lint.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/lint.yaml)
[![tests](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/tests.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/tests.yaml)
[![codecov](https://codecov.io/gh/plasma-ai/mdformat-wiki/branch/main/graph/badge.svg?token=hOhrWzJqNu)](https://codecov.io/gh/plasma-ai/mdformat-wiki)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Mdformat plugin preserving wikilinks, frontmatter, and index delimiter.

Built for wikis created with
[plasma-wiki](https://github.com/plasma-ai/wiki) — add it wherever
mdformat runs over a wiki maintained by `plasma-wiki`.

______________________________________________________________________

**Source**:
[https://github.com/plasma-ai/mdformat-wiki](https://github.com/plasma-ai/mdformat-wiki)

**Package**:
[https://pypi.org/project/mdformat-wiki/](https://pypi.org/project/mdformat-wiki/)

______________________________________________________________________

## Installation

Install the `mdformat-wiki` package from PyPI, alongside
[mdformat](https://mdformat.readthedocs.io):

```bash
pip install mdformat-wiki
```

Use `uv tool install mdformat --with mdformat-wiki` to install in an
isolated environment.

## Usage

Once installed, mdformat picks the plugin up automatically and stops
disturbing wiki page faces:

- `[[...]]` wikilinks parse atomically (single line, no nesting) and are
  never backslash-escaped — including the `[[target|label]]` pipe form.
- Wikilinks are wrap-atomic: under `--wrap`, the whole `[[...]]` face
  moves between lines as one unit, like an inline code span, while the
  prose around it fills normally.
- YAML frontmatter at the start of a document renders byte-verbatim
  (fences and content untouched).
- A thematic break written exactly as `***` keeps that face; every other
  break style is normalized as usual.

### pre-commit

Repos that format markdown with a [pre-commit](https://pre-commit.com)
hook need one line — add the plugin to the mdformat hook's
`additional_dependencies`:

```yaml
  - repo: https://github.com/hukkin/mdformat
    rev: 1.0.0
    hooks:
      - id: mdformat
        additional_dependencies: [mdformat-wiki]
```

If the hook already lists
[mdformat-frontmatter](https://github.com/butler54/mdformat-frontmatter),
remove it — this plugin already renders frontmatter byte-verbatim. Both
plugins register a frontmatter renderer, mdformat only warns about the
conflict, and whichever the environment discovers first wins: when
`mdformat-frontmatter` wins, it re-serializes the YAML (quoting values,
blanking `null`s) instead of leaving it untouched.

### Footnotes

Baseline mdformat escapes footnote definitions (`[^1]:` becomes
`\[^1\]:`). If your pages use footnotes, add
[mdformat-footnote](https://github.com/executablebooks/mdformat-footnote)
alongside this plugin — the two compose cleanly (definitions relocate to
the document bottom, which is semantically neutral).

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

## License

Licensed under the Apache License 2.0 — see [LICENSE](LICENSE).

Copyright © 2026 Plasma AI
