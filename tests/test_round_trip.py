"""Round-trip tests: formatting a wiki face is a byte-identical no-op."""

from __future__ import annotations

import pathlib

import mdformat
import pytest

__all__ = [
    'test_round_trip',
    'test_front_matter_faces',
    'test_thematic_break_faces',
    'test_thematic_break_in_blockquote_defaults',
    'test_footnote_composition',
]

_FIXTURES = pathlib.Path(__file__).parent / 'fixtures'
# every corpus file must survive a format pass byte-identically
_ROUND_TRIP_CORPUS = [
    'wiki/_index.md',
    'wiki/topics/_index.md',
    'wiki/topics/alpha.md',
    'wiki/topics/beta.md',
    'obsidian.md',
    'gaphunt.md',
    'code-fences.md',
]
# mdformat's default thematic-break face (what non-``***`` sources become)
_DEFAULT_HR = '_' * 70


@pytest.mark.parametrize('relpath', _ROUND_TRIP_CORPUS)
def test_round_trip(relpath: str) -> None:
    """Formatting a corpus file is byte-identical and idempotent.

    The corpora cover the generated wiki faces (frontmatter, wikilink
    blocks, the ``***`` delimiter), Obsidian body constructs (embeds,
    callouts, block refs, tags), tables/tasklists/footnote refs, and
    code fences containing ``[[...]]``.
    """
    source = (_FIXTURES / relpath).read_text(encoding='utf-8')
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


@pytest.mark.parametrize(
    'source',
    [
        '---\nname: x\n\n---\n\nbody\n',
        '---\nname: x  \n---\n\nbody\n',
        '----\nname: x\n----\n\nbody\n',
        '-----\nname: x\n---------\n\nbody\n',
    ],
    ids=['trailing-blank-line', 'trailing-spaces', 'four-dashes', 'longer-close'],
)
def test_front_matter_faces(source: str) -> None:
    """Pathological-but-valid frontmatter still renders byte-verbatim.

    Trailing blank lines or whitespace inside the block and 4+-dash
    fences are all accepted by the ``mdit-py-plugins`` grammar, so the
    fences + content untouched contract covers them too.
    """
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


@pytest.mark.parametrize(
    ('source_line', 'rendered_line'),
    [
        ('***', '***'),
        ('  ***', '***'),
        ('*****', _DEFAULT_HR),
        ('* * *', _DEFAULT_HR),
        ('---', _DEFAULT_HR),
        ('___', _DEFAULT_HR),
    ],
    ids=['bare', 'indented', 'five-stars', 'spaced', 'dashes', 'underscores'],
)
def test_thematic_break_faces(source_line: str, rendered_line: str) -> None:
    """Only a source line that strips to ``***`` keeps that face."""
    source = f'above\n\n{source_line}\n\nbelow\n'
    expected = f'above\n\n{rendered_line}\n\nbelow\n'
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == expected

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


def test_thematic_break_in_blockquote_defaults() -> None:
    """A ``***`` nested in a blockquote falls back to the default face."""
    formatted = mdformat.text('> ***\n', extensions={'wiki'})
    assert formatted == f'> {_DEFAULT_HR}\n'


def test_footnote_composition() -> None:
    """``mdformat-footnote`` composes: definitions survive un-escaped."""
    source = (
        '# Notes\n'
        '\n'
        'Footnote ref[^1] and another[^note].\n'
        '\n'
        '[^1]: A multi word footnote body.\n'
        '\n'
        'Trailing prose with a [[topics/alpha]] link.\n'
        '\n'
        '[^note]: word\n'
    )
    formatted = mdformat.text(source, extensions={'wiki', 'footnote'})

    # definitions survive un-escaped (relocation to the bottom is fine)
    assert '\\[^' not in formatted
    assert '[^1]: A multi word footnote body.' in formatted
    assert '[^note]: word' in formatted

    # wikilinks stay atomic under composition
    assert '[[topics/alpha]]' in formatted

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki', 'footnote'})
    assert second == formatted
