"""Round-trip tests: formatting a wiki face is a byte-identical no-op."""

from __future__ import annotations

import pathlib
import re

import mdformat
import pytest

__all__ = [
    'test_round_trip',
    'test_front_matter_faces',
    'test_frontmatter_bom_is_normalized_away',
    'test_frontmatter_indented_dash_run_is_block_scalar_content',
    'test_non_wiki_fences_are_not_frontmatter',
    'test_frontmatter_in_blockquote_is_body',
    'test_thematic_break_faces',
    'test_thematic_break_in_blockquote_defaults',
    'test_heading_faces',
    'test_heading_in_blockquote_defaults',
    'test_heading_in_list_keeps_face',
    'test_link_row_desc_faces',
    'test_link_row_dash_run_is_desc_content',
    'test_link_row_keeps_trailing_hard_breaks',
    'test_non_row_prose_still_escapes',
    'test_verbatim_faces_keep_reference_definitions',
    'test_non_wikilink_brackets_use_healthy_escape',
    'test_wikilink_wrap_atomicity',
    'test_link_row_multiline_escapes_survive',
    'test_link_row_in_blockquote_defaults',
    'test_bare_target_paragraph_is_prose',
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
# mdformat's default thematic-break face (what non-*** sources become)
_DEFAULT_HR = '_' * 70


# ------ round trip


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


# ------ frontmatter


@pytest.mark.parametrize(
    argnames='source',
    argvalues=[
        '---\nname: x\n\n---\n\nbody\n',
        '---\nname: x  \n---\n\nbody\n',
        '  ---\nname: x\n---\n\nbody\n',
        '---\nname: x\n---  \n\nbody\n',
    ],
    ids=[
        'trailing-blank-line',
        'trailing-spaces',
        'indented-open',
        'close-trailing-spaces',
    ],
)
def test_front_matter_faces(source: str) -> None:
    """Pathological-but-valid frontmatter still renders byte-verbatim.

    Blank lines and trailing whitespace inside the block, whitespace
    around the opening fence, and trailing whitespace after the closing
    fence are all tolerated by the wiki reader's grammar, so the
    fences + content untouched contract covers them too.
    """
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


def test_frontmatter_bom_is_normalized_away() -> None:
    """A UTF-8 BOM before the opening fence is stripped, frontmatter kept.

    The front-matter block rule matches ``---`` only at column 0 of line 0, so
    a leading BOM would push the whole block into prose and re-render it as a
    heading, silently destroying the frontmatter. The BOM normalizes away
    (mirroring the wiki merge driver) while the frontmatter renders verbatim.
    """
    source = '\ufeff---\nname: alpha\ndesc: A page.\n---\n\n# Alpha\n'
    expected = '---\nname: alpha\ndesc: A page.\n---\n\n# Alpha\n'
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == expected

    # the BOM is gone, so the stripped output now round-trips
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


def test_frontmatter_indented_dash_run_is_block_scalar_content() -> None:
    """An indented dash run inside a block scalar does not close the fence.

    Only an unindented ``---`` closes frontmatter (matching the wiki
    reader): a separator rule inside a block-scalar desc is content, so
    the block survives intact instead of truncating there and silently
    demoting the remaining keys to body.
    """
    source = (
        '---\n'
        'name: alpha\n'
        'desc: |\n'
        '  A separator rule follows in the desc:\n'
        '  ----------\n'
        '  and more desc after it.\n'
        'tags: [x]\n'
        '---\n'
        '\n'
        '# Alpha\n'
    )
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    # wrapping reflows only body prose, never the frontmatter
    wrapped = mdformat.text(source, options={'wrap': 72}, extensions={'wiki'})
    assert wrapped == source


@pytest.mark.parametrize(
    argnames='source',
    argvalues=[
        '----\nname: x\n----\n\nbody\n',
        '-----\nname: x\n---------\n\nbody\n',
        '---\nname: x\nbody text\n',
        '---\nname: x\n...\nbody\n',
    ],
    ids=['four-dashes', 'longer-close', 'unclosed', 'yaml-dots-close'],
)
def test_non_wiki_fences_are_not_frontmatter(source: str) -> None:
    """Fences the wiki reader rejects parse as body, not frontmatter.

    The wiki grammar opens only on a line stripping to exactly ``---``
    and closes only on an unindented one, so 4+-dash fences, a YAML
    ``...`` line, and an unclosed opener leave the file
    frontmatter-less. The text formats as ordinary body markdown
    instead of freezing a block the wiki reads as content.
    """
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted.startswith(_DEFAULT_HR)
    assert 'name: x' in formatted

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


def test_frontmatter_in_blockquote_is_body() -> None:
    """A quoted dash fence opening the document is body, not frontmatter.

    The wiki reader sees ``> ---`` on line 0, not a fence, so the rule
    must not match inside the blockquote -- a verbatim slice of the
    still-prefixed source lines would gain another ``> `` from the
    container renderer, doubling the markers on every pass.
    """
    source = '> ---\n> name: x\n> ---\n'
    expected = f'> {_DEFAULT_HR}\n>\n> ## name: x\n'
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == expected

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


# ------ thematic breaks


@pytest.mark.parametrize(
    argnames=('source_line', 'rendered_line'),
    argvalues=[
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


# ------ headings


@pytest.mark.parametrize(
    argnames=('source_head', 'rendered_head'),
    argvalues=[
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


# ------ link rows


@pytest.mark.parametrize(
    argnames=('source_row', 'rendered_row'),
    argvalues=[
        (
            '[[api/kwargs|kwargs]]: Accepts **kwargs and _verb helpers.',
            '[[api/kwargs|kwargs]]: Accepts **kwargs and _verb helpers.',
        ),
        (
            '[[docs/index-pages|index-pages]]: The _index.md block above'
            ' the *** delimiter.',
            '[[docs/index-pages|index-pages]]: The _index.md block above'
            ' the *** delimiter.',
        ),
    ],
    ids=['emphasis-markers', 'underscores-and-hr'],
)
def test_link_row_desc_faces(source_row: str, rendered_row: str) -> None:
    """An index link-row desc renders face-verbatim, never escaped.

    A desc is plain prose whose bare ``*`` or ``_`` (``**kwargs``,
    ``_verb``) would otherwise gain a backslash and diverge the row from
    the page's frontmatter desc, so the wiki tool overwrites it and the
    two formatters fight. Ordinary prose keeps the default escaping.
    """
    source = f'{source_row}\n'
    expected = f'{rendered_row}\n'
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == expected

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


@pytest.mark.parametrize(
    argnames='desc_line',
    argvalues=['----------', '---', '==========', '----|----'],
    ids=['dash-run', 'three-dashes', 'equals-run', 'piped-dashes'],
)
def test_link_row_dash_run_is_desc_content(desc_line: str) -> None:
    """A dash-run desc continuation is row content, not a setext underline.

    The wiki writes a block-scalar page desc's separator rule at column
    0 inside the link block, where block markdown would read it as a
    setext underline (or, piped, a table delimiter) and turn the row
    into a heading -- the entry would vanish from the block on the next
    wiki read. The row parses atomically, so the run stays verbatim desc
    content under both wrap modes.
    """
    source = (
        '[[topics/alpha|alpha]]: Overview of alpha:\n'
        f'{desc_line}\n'
        'and more desc after it.\n'
        '\n'
        '[[topics/beta|beta]]: Beta desc.\n'
    )
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    wrapped = mdformat.text(source, options={'wrap': 72}, extensions={'wiki'})
    assert wrapped == source


def test_link_row_keeps_trailing_hard_breaks() -> None:
    """A row's trailing hard-break spaces round-trip byte-verbatim.

    Two trailing spaces are a hard line break: stripping them changes
    the rendered HTML, and mdformat's equivalence check then refuses
    the whole file with a misdiagnosis naming mdformat itself -- a
    hand-authored break inside a row must instead pass through like
    every other row byte.
    """
    source = '[[topics/alpha|alpha]]: desc with a break  \ncontinuation  \n'
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


def test_non_row_prose_still_escapes() -> None:
    """Only a link-row desc bypasses escaping; ordinary prose does not."""
    formatted = mdformat.text('Prose with **kwargs and _verb.\n', extensions={'wiki'})
    assert formatted == 'Prose with \\*\\*kwargs and \\_verb.\n'


# ------ reference definitions


@pytest.mark.parametrize(
    argnames='source',
    argvalues=[
        '# The [architecture][arch] overview\n'
        '\n'
        'body\n'
        '\n'
        '[arch]: https://example.com/doc\n',
        '# Diagram ![alt][img] inline\n'
        '\n'
        'body\n'
        '\n'
        '[img]: https://example.com/diagram.png\n',
        '[[topics/alpha|alpha]]: See the [architecture][arch] notes.\n'
        '\n'
        '[arch]: https://example.com/doc\n',
    ],
    ids=['heading-link', 'heading-image', 'link-row-link'],
)
def test_verbatim_faces_keep_reference_definitions(source: str) -> None:
    """A reference used only inside a verbatim face keeps its definition.

    The verbatim heading and link-row renderers return the source face
    without descending into the inline children, whose default renderers
    are what mark a reference label as used -- the labels register
    explicitly instead, or mdformat would drop the ``[label]: url``
    definition from the output, permanently deleting the URL.
    """
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


# ------ bracket escaping


@pytest.mark.parametrize(
    argnames=('source', 'expected'),
    argvalues=[
        (
            'See [[topics/alpha for details.\n',
            'See [\\[topics/alpha for details.\n',
        ),
        ('A [[[weird bracket run.\n', 'A [[\\[weird bracket run.\n'),
        ('x [[foo] bar.\n', 'x [[foo] bar.\n'),
        (
            '[[label]: x\n\n[label]: http://e.com\n',
            '[[label]: x\n\n[label]: http://e.com\n',
        ),
        ('See [[foo](bar) here.\n', 'See [[foo](bar) here.\n'),
    ],
    ids=[
        'unclosed',
        'triple-run',
        'bare-pair',
        'used-ref-pair',
        'link-adjacency',
    ],
)
def test_non_wikilink_brackets_use_healthy_escape(source: str, expected: str) -> None:
    r"""A non-wikilink ``[[`` escapes healthily, never as ``\[[``/``\[\[``.

    The wiki's lint reads a backslash before double brackets as the
    signature of formatter damage to a real wikilink, so the sanctioned
    formatter must never produce it: in a bracket run only the last
    ``[`` keeps its escape (``[\[``, matching the wiki's
    ``escape_desc``), and a lone escape before a link token is bared.
    Stability holds either way -- every output re-parses to the same
    tokens.
    """
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == expected
    assert re.search(r'\\\[\\?\[', formatted) is None

    # second pass is stable
    second = mdformat.text(formatted, extensions={'wiki'})
    assert second == formatted


# ------ wrapping


@pytest.mark.parametrize(
    argnames=('source', 'expected'),
    argvalues=[
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
            ' that pushes this link row well past seventy-two columns.\n',
        ),
        (
            'A long prose paragraph that mentions [[topics/alpha]] midway'
            ' through and therefore wraps like any other body paragraph.\n',
            'A long prose paragraph that mentions [[topics/alpha]] midway'
            ' through and\ntherefore wraps like any other body paragraph.\n',
        ),
    ],
    ids=[
        'spaced-label-moves-whole',
        'link-row-desc-verbatim',
        'prose-wraps',
    ],
)
def test_wikilink_wrap_atomicity(source: str, expected: str) -> None:
    """Wikilinks are wrap-atomic; prose wraps while link rows never do.

    A wikilink behaves like an inline code span under ``--wrap``: its
    internal spaces are never wrap points, so the whole ``[[...]]``
    face moves between lines as one unit while the prose around it
    fills normally. An index link row is structured data and renders
    verbatim -- no part of it wraps.
    """
    formatted = mdformat.text(source, options={'wrap': 72}, extensions={'wiki'})
    assert formatted == expected

    # second pass is stable
    second = mdformat.text(formatted, options={'wrap': 72}, extensions={'wiki'})
    assert second == formatted


def test_link_row_multiline_escapes_survive() -> None:
    r"""A link row's ``escape_desc`` continuations round-trip untouched.

    The wiki escapes desc continuation lines that would parse as index
    structure (``\***`` for the delimiter, ``[\[`` for a link-shaped
    line). The row block renders verbatim, so the escapes and line
    breaks survive under both wrap modes -- decoding them would
    oscillate the index against ``wiki update``, and the decoded desc
    line would re-parse as a real wikilink (different HTML, a
    formatting abort). Byte-identical output means ``--check`` passes.
    """
    source = '[[alpha|Alpha]]: First line.\n\\***\n[\\[other|p]]: not a real link.\n'
    formatted = mdformat.text(source, extensions={'wiki'})
    assert formatted == source

    wrapped = mdformat.text(source, options={'wrap': 72}, extensions={'wiki'})
    assert wrapped == source


def test_link_row_in_blockquote_defaults() -> None:
    """A link row nested in a blockquote falls back to the default path.

    The verbatim renderer only fires at top level: a container
    re-prefixes its children's rendered lines (``> ``), which would
    double on a verbatim slice of source lines already carrying it.
    """
    formatted = mdformat.text('> [[a|b]]: quoted row.\n', extensions={'wiki'})
    assert formatted == '> [[a|b]]: quoted row.\n'


def test_bare_target_paragraph_is_prose() -> None:
    """A paragraph opening ``[[target]]: ...`` (no label pipe) is prose.

    The wiki row grammar requires ``[[target|label]]``, so a bare-target
    opener is body text that keeps normal formatting (here, whitespace
    normalization) rather than freezing verbatim.
    """
    formatted = mdformat.text('[[alpha]]: some  text.\n', extensions={'wiki'})
    assert formatted == '[[alpha]]: some text.\n'


# ------ footnotes


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
