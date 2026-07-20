# mdformat-wiki

[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/plasma-ai/mdformat-wiki/blob/main/LICENSE)
[![build](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/build.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/build.yaml)
[![lint](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/lint.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/lint.yaml)
[![tests](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/tests.yaml/badge.svg)](https://github.com/plasma-ai/mdformat-wiki/actions/workflows/tests.yaml)
[![codecov](https://codecov.io/gh/plasma-ai/mdformat-wiki/branch/main/graph/badge.svg?token=hOhrWzJqNu)](https://codecov.io/gh/plasma-ai/mdformat-wiki)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Mdformat plugin preserving wikilinks, frontmatter, and index delimiter.

Built for wikis created with [plasma-wiki](https://github.com/plasma-ai/wiki) —
add it wherever mdformat runs over a wiki maintained by `plasma-wiki`.

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

Use `uv tool install mdformat --with mdformat-wiki` to install in an isolated
environment.

## Usage

Once installed, mdformat picks the plugin up automatically and stops disturbing
wiki page faces:

- `[[...]]` wikilinks parse atomically (single line, no nesting) and are never
  backslash-escaped — including the `[[target|label]]` pipe form.
- Wikilinks are wrap-atomic: under `--wrap`, the whole `[[...]]` face moves
  between lines as one unit, like an inline code span, while the prose around it
  fills normally.
- YAML frontmatter renders byte-verbatim (fences and content untouched), with
  the fence grammar matching the wiki reader exactly: the opener is the first
  line stripping to `---`, only an unindented `---` closes (an indented dash run
  inside a block scalar is content), and `----`/`...` fences or an unclosed
  opener are not frontmatter. A leading UTF-8 BOM is normalized away.
- A thematic break written exactly as `***` keeps that face; every other break
  style is normalized as usual.
- ATX headings keep their original inline face verbatim — unbalanced emphasis is
  never backslash-escaped and an optional closing `#` sequence survives; setext
  headings still normalize to ATX.
- An index link row (`[[target|label]]: description`) renders verbatim, line
  breaks and escapes intact — a bare `*` or `_` (`**kwargs`, `_verb`) is never
  backslash-escaped, and the row never reflows under `--wrap`. The link block is
  the wiki's structured data; its bytes round-trip.
- A non-wikilink `[[` in body prose (an unclosed `[[foo`, a bracket run) escapes
  in the healthy `[\[` shape — never the `\[[` shape the wiki's lint flags as
  formatter damage.

### Pre-commit Hook

Repos that format markdown with a [pre-commit](https://pre-commit.com) hook need
one line — add the plugin to the mdformat hook's `additional_dependencies`:

```yaml
  - repo: https://github.com/hukkin/mdformat
    rev: 1.0.0
    hooks:
      - id: mdformat
        additional_dependencies: [mdformat-wiki]
```

If the hook already lists
[mdformat-frontmatter](https://github.com/butler54/mdformat-frontmatter), remove
it — this plugin already renders frontmatter byte-verbatim. Both plugins
register a frontmatter renderer, mdformat only warns about the conflict, and
whichever the environment discovers first wins: when `mdformat-frontmatter`
wins, it re-serializes the YAML (quoting values, blanking `null`s) instead of
leaving it untouched.

### Footnotes

Baseline mdformat escapes footnote definitions (`[^1]:` becomes `\[^1\]:`). If
your pages use footnotes, add
[mdformat-footnote](https://github.com/executablebooks/mdformat-footnote)
alongside this plugin — the two compose cleanly (definitions relocate to the
document bottom, which is semantically neutral).

## Development

### Install

Run `install.sh` in the package root. With no environment active it creates and
uses a local `.venv`; with one active (e.g. pyenv) it installs into that
environment (editable), without recreating it:

```bash
./install.sh --all-extras --groups=test,lint,type
```

Run `./install.sh --help` for all options. Alternatively, run
`uv sync --all-extras --group test --group lint --group type` and
`uv run pre-commit install` to set up the environment manually.

Installing a dependency as editable (e.g. a sibling package) is left to the
caller: `uv pip install --editable <path>`.

Once installed, run tools with `uv run --no-sync <command>`, or activate the
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

### Contributing

The contribution workflow, repository conventions, and release process (version
sources, tagging, CI guard) are documented in:

- Contribution workflow (organization-wide):
  [CONTRIBUTING.md](https://github.com/plasma-ai/.github/blob/main/CONTRIBUTING.md)
- Repository conventions:
  [AGENTS.md](https://github.com/plasma-ai/mdformat-wiki/blob/main/AGENTS.md)
- Release process (organization-wide):
  [RELEASING.md](https://github.com/plasma-ai/.github/blob/main/RELEASING.md)

## License

Licensed under the Apache License 2.0 — see
[LICENSE](https://github.com/plasma-ai/mdformat-wiki/blob/main/LICENSE).

Copyright © 2026 Plasma AI
