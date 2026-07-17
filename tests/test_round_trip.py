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
    'test_heading_faces',
    'test_heading_in_blockquote_defaults',
    'test_heading_in_list_keeps_face',
    'test_wikilink_wrap_atomicity',
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
    'headings.md',
]
# mdformat's default thematic-break face (what non-``***`` sources become)
_DEFAULT_HR = '_' * 70


@pytest.mark.parametrize('relpath', _ROUND_TRIP_CORPUS)
def test_round_trip(relpath: str) -> None:
    """Formatting a corpus file is byte-identical and idempotent.

    The corpora cover the generated wiki faces (frontmatter, wikilink
    blocks, the ``***`` delimiter), Obsidian body constructs (embeds,
    callouts, block refs, tags), tables/tasklists/footnote refs, code
    fences containing ``[[...]]``, and adversarial ATX heading faces.
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


@pytest.mark.parametrize(
    ('source_head', 'rendered_head'),
    [
        ('# Star* dangling *star', '# Star* dangling *star'),
        ('# Trailing hash #', '# Trailing hash #'),
        ('# My *Wiki*', '# My *Wiki*'),
        ('# snake_case_title', '# snake_case_title'),
        ('# Brackets [not a link]', '# Brackets [not a link]'),
        ('# Code `span`', '# Code `span`'),
        ('  # Indented face', '# Indented face'),
        ('Setext face\n===========', '# Setext face'),
    ],
    ids=[
        'dangling-star',
        'trailing-hash',
        'balanced-emphasis',
        'underscores',
        'brackets',
        'backticks',
        'indented',
        'setext',
    ],
)
def test_heading_faces(source_head: str, rendered_head: str) -> None:
    """An ATX heading keeps its source face; only its indent normalizes.

    Unbalanced emphasis is never backslash-escaped and an optional
    closing ``#`` sequence survives, while a setext heading still
    normalizes to the default ATX face.
    """
    source = f'{source_head}\n\nbody\n'
    expected = f'{rendered_head}\n\nbody\n'
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == expected

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


def test_heading_in_blockquote_defaults() -> None:
    """A heading nested in a blockquote falls back to the default face."""
    formatted = mdformat.text('> # Star* dangling *star\n', extensions={'wiki'})
    assert formatted == '> # Star\\* dangling \\*star\n'


def test_heading_in_list_keeps_face() -> None:
    """A heading on a list continuation line keeps its source face.

    The continuation line strips to the bare ATX face, so the verbatim
    path applies even inside a container; a heading sharing its list
    marker's line does not strip to it and falls back to the default
    face.
    """
    source = '- item\n\n  # Star* dangling *star\n'
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    # a heading on the marker's own line delegates
    marker = mdformat.text('- # Star* dangling *star\n', extensions={'wiki'})
    assert marker == '- # Star\\* dangling \\*star\n'


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        (
            'Prose that runs long enough to push the following'
            ' [[conventions/python/modules|python module shape]] link'
            ' across the boundary.\n',
            'Prose that runs long enough to push the following\n'
            '[[conventions/python/modules|python module shape]] link'
            ' across the\nboundary.\n',
        ),
        (
            '[[topics/beta|beta]]: A deliberately long generated description'
            ' that pushes this link row well past seventy-two columns.\n',
            '[[topics/beta|beta]]: A deliberately long generated description'
            ' that\npushes this link row well past seventy-two columns.\n',
        ),
        (
            'A long prose paragraph that mentions [[topics/alpha]] midway'
            ' through and therefore wraps like any other body paragraph.\n',
            'A long prose paragraph that mentions [[topics/alpha]] midway'
            ' through and\ntherefore wraps like any other body paragraph.\n',
        ),
    ],
    ids=['spaced-label-moves-whole', 'link-row-tail-wraps', 'prose-wraps'],
)
def test_wikilink_wrap_atomicity(source: str, expected: str) -> None:
    """Wikilinks are wrap-atomic; surrounding prose wraps freely.

    A wikilink behaves like an inline code span under ``--wrap``: its
    internal spaces are never wrap points, so the whole ``[[...]]``
    face moves between lines as one unit while the text around it --
    including a link row's description tail -- fills normally.
    """
    formatted = mdformat.text(source, options={'wrap': 72}, extensions={'wiki'})
    assert formatted == expected

    # second pass is stable
    second = mdformat.text(formatted, options={'wrap': 72}, extensions={'wiki'})
    assert second == formatted


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
