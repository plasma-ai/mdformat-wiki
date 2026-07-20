"""The mdformat parser extension: wiki syntax rules and renderers.

mdformat discovers ``update_mdit`` and ``RENDERERS`` on this module
through the ``mdformat.parser_extension`` entry point declared in
``pyproject.toml``.
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock
from markdown_it.rules_core import StateCore
from markdown_it.rules_inline import StateInline
from mdformat.renderer import DEFAULT_RENDERERS, RenderContext, RenderTreeNode

__all__ = [
    'update_mdit',
    'RENDERERS',
]

# env key for the source lines stashed at parse time (see the renderers)
_SRC_LINES = 'mdformat_wiki_src_lines'

# a row line whose break placement is load-bearing, kept verbatim by the
# row wrap: an escape_desc face (leading backslash or escaped bracket),
# a structure-shaped opener a generic renderer would misread mid-join
# (a bare thematic/setext run, headings, quotes, lists, tables, fences,
# a row-shaped face the reader could take for a fresh entry), or a
# hard-break tail (trailing double space or backslash); a dash run
# followed by text (`-- like this`) is plain prose and refills freely
_HAZARD_OPEN = re.compile(
    r'^(\\|\[\\\[|\[\[[^]]*\|[^]]*\]\]:|#{1,6}(\s|$)|>|\||[-*+]\s|\d+[.)]\s'
    r'|```|~~~)'
)
_HARD_BREAK_TAIL = re.compile(r'(  |\\)$')
_FROZEN_ROW_LINE = re.compile(
    _HAZARD_OPEN.pattern
    + r'|^[|: ]*[-=*_]{2,}[-=*_|: ]*$'
    + f'|{_HARD_BREAK_TAIL.pattern}'
)

# a bare setext/thematic run or piped table-delimiter shape -- never
# emitted alone on a wrapped line
_PURE_RUN = re.compile(r'[|:]*[-=*_]{2,}[-=*_|:]*')

# one wrap atom: a whole [[...]] face with its colon tail, else a word
_ROW_ATOM = re.compile(r'\[\[[^]]*\]\]\S*|\S+')


def update_mdit(mdit: MarkdownIt) -> None:
    """Register the wiki syntax rules on the markdown-it parser.

    Adds front-matter and link-row block rules matching the wiki
    reader's grammar, an atomic ``[[...]]`` wikilink inline rule, and
    core rules normalizing a leading BOM and stashing the source lines
    for face-sensitive rendering.

    Args:
        mdit: Parser to extend, one per document mdformat formats.

    """
    # register the front-matter block rule
    mdit.block.ruler.before(
        beforeName='table',
        ruleName='front_matter',
        fn=_frontmatter_rule,
        options={'alt': ['paragraph', 'reference', 'blockquote', 'list']},
    )
    # register the link-row block rule
    mdit.block.ruler.before(
        beforeName='table',
        ruleName='link_row',
        fn=_link_row_rule,
    )
    # register the atomic wikilink inline rule
    mdit.inline.ruler.before('link', 'wikilink', _wikilink_rule)
    # register the BOM-normalizing core rule
    mdit.core.ruler.before('block', 'wiki_strip_bom', _strip_bom)
    # register the source-stashing core rule
    mdit.core.ruler.push('wiki_stash_src', _stash_src)


def _frontmatter_rule(
    state: StateBlock,
    start_line: int,
    end_line: int,
    silent: bool,
) -> bool:
    """Parse frontmatter with the wiki reader's fence grammar.

    The opener is line 0 stripping to exactly ``---``, at the top
    level only -- inside a container the line numbers stay absolute
    while the marks skip the container markup, but the raw face still
    carries it (``> ---``), so the wiki reader sees body there. Only
    an unindented line stripping to ``---`` closes the block. An indented
    dash run is block-scalar content, not a fence -- a closer that
    skips indentation would truncate the frontmatter there, silently
    demoting the rest to body. No closer means no frontmatter (the wiki
    reads the whole file as body), and a YAML ``...`` line never
    closes. A leading BOM is already normalized away
    (``wiki_strip_bom`` runs before the block phase).

    Args:
        state: Block parser state, positioned at the candidate opener.
        silent: Probe for a match without emitting the token.

    Returns:
        Whether a frontmatter block was consumed.

    """
    # opener: top-level line 0 only, stripping to exactly ---
    # (inside a container the marks skip the container markup, but the
    # raw face carries it, so the wiki reader sees body there)
    if (start_line != 0) or (state.parentType != 'root'):
        return False
    first = state.src[state.bMarks[0] : state.eMarks[0]]
    if first.strip() != '---':
        return False
    if silent:
        return True
    # closer: the next line stripping to --- at column 0
    # (an indented dash run is block-scalar content)
    next_line = start_line
    while True:
        next_line += 1
        if next_line >= end_line:
            return False
        if state.sCount[next_line] != 0:
            continue
        line = state.src[state.bMarks[next_line] : state.eMarks[next_line]]
        if line.rstrip() == '---':
            break
    # emit the hidden front-matter token
    token = state.push('front_matter', '', 0)
    token.hidden = True
    token.markup = '---'
    token.content = state.src[
        state.bMarks[start_line + 1] : state.eMarks[next_line - 1]
    ]
    token.block = True
    token.map = [start_line, next_line + 1]
    # advance past the closer
    state.line = next_line + 1
    # return the match
    return True


def _link_row_rule(
    state: StateBlock,
    start_line: int,
    end_line: int,
    silent: bool,
) -> bool:
    r"""Parse an index link row (``[[t|l]]: ...``) as one atomic block.

    A link block is structured data: the ``[[t|l]]`` faces, the
    ``escape_desc`` backslashes on continuation lines (``\***``/``[\[``),
    and every load-bearing line break round-trip unchanged, so the wiki
    reader reads back exactly what it wrote and the index converges
    (plain prose lines may refill to a numeric wrap column -- see
    :func:`_wrap_link_row`). To the
    reader every contiguous non-blank line under the row is desc
    continuation, but to block markdown some are structure -- a dash-run
    line is a setext underline that would turn the row into a heading
    (deleting the entry from the block) and a piped dash run would make
    the row a table header -- so the row consumes its whole run before
    those rules can see it. The label pipe and the colon are both
    mandatory, mirroring the reader's row grammar: a body paragraph
    opening with a bare ``[[target]]`` is prose. Only a top-level row
    qualifies: a container re-prefixes its rendered lines (``> ``),
    which would double on a verbatim slice. The token pair nests an
    ``inline`` child like a paragraph's, so the desc still inline-parses
    in the core phase (after reference collection) and the renderer can
    register its reference labels as used.

    Args:
        state: Block parser state, positioned at the candidate opener.
        silent: Probe for a match without emitting the token.

    Returns:
        Whether a link row was consumed.

    """
    # only a top-level, non-code line can open a row (nesting depth, not
    # parentType, which a rejected lheading probe leaves as 'paragraph')
    if (state.level != 0) or state.is_code_block(start_line):
        return False
    # opener: an atomic [[...]] face carrying the label pipe, with the
    # colon tail directly after the closer
    first = state.src[
        state.bMarks[start_line] + state.tShift[start_line] : state.eMarks[start_line]
    ]
    if not first.startswith('[['):
        return False
    closer = first.find(']]', 2)
    if closer == -1:
        return False
    if ('|' not in first[2:closer]) or (first[closer + 2 : closer + 3] != ':'):
        return False
    if silent:
        return True
    # consume the contiguous non-blank run
    next_line = start_line + 1
    while (next_line < end_line) and not state.isEmpty(next_line):
        next_line += 1
    # emit the link-row token pair around the desc's inline child
    token = state.push('link_row_open', '', 1)
    token.content = state.src[state.bMarks[start_line] : state.eMarks[next_line - 1]]
    token.map = [start_line, next_line]
    token = state.push('inline', '', 0)
    token.content = state.getLines(
        start_line, next_line, state.blkIndent, False
    ).strip()
    token.map = [start_line, next_line]
    token.children = []
    state.push('link_row_close', '', -1)
    # advance past the row
    state.line = next_line
    # return the match
    return True


def _strip_bom(state: StateCore) -> None:
    """Drop a leading UTF-8 BOM so the front-matter rule matches at line 0.

    The front-matter block rule opens only on line 0 stripping to ``---``,
    and a BOM (which markdown-it's normalize leaves in place, and the wiki
    reader tolerates) is not whitespace -- the whole block would parse as
    prose and re-render as a heading, silently destroying the frontmatter.
    Normalizing the BOM away here (mirroring the wiki merge driver) keeps
    the frontmatter.
    """
    if state.src.startswith('\ufeff'):
        state.src = state.src[1:]


def _stash_src(state: StateCore) -> None:
    """Stash the source lines into ``env`` for the renderers."""
    state.env[_SRC_LINES] = state.src.split('\n')


def _wikilink_rule(state: StateInline, silent: bool) -> bool:
    """Parse ``[[...]]`` as one atomic token (single line, no nesting).

    Runs before the ``link`` rule so bracketed targets never reach the
    escaping-sensitive link parser. Consuming means advancing
    ``state.pos`` past the closer; in silent mode the parser is only
    probing, so the token must not be pushed.

    Args:
        state: Inline parser state, positioned at the candidate opener.
        silent: Probe for a match without emitting the token.

    Returns:
        Whether a wikilink was consumed.

    """
    # alias source and position
    src = state.src
    pos = state.pos
    # check the opener
    if src[pos : pos + 2] != '[[':
        return False
    # find the closer on the same line
    end = src.find(']]', pos + 2)
    if (end == -1) or ('\n' in src[pos + 2 : end]):
        return False
    # emit the atomic wikilink token
    if not silent:
        token = state.push('wikilink', '', 0)
        token.content = src[pos + 2 : end]
    # advance past the closer
    state.pos = end + 2
    # return the match
    return True


def _render_wikilink(node: RenderTreeNode, context: RenderContext) -> str:
    """Render a wikilink back to its literal ``[[...]]`` face."""
    return f'[[{node.content}]]'


def _render_front_matter(node: RenderTreeNode, context: RenderContext) -> str:
    """Render frontmatter byte-verbatim, fences and content untouched."""
    lines = context.env.get(_SRC_LINES)
    if (lines is not None) and (node.map is not None):
        region = lines[node.map[0] : node.map[1]]
        return '\n'.join(region)
    return f'---\n{node.content}\n---'


def _render_hr(node: RenderTreeNode, context: RenderContext) -> str:
    """Render a thematic break, preserving only the literal ``***`` face."""
    lines = context.env.get(_SRC_LINES)
    if (lines is not None) and (node.map is not None):
        if lines[node.map[0]].strip() == '***':
            return '***'
    return DEFAULT_RENDERERS['hr'](node, context)


def _register_refs(node: RenderTreeNode, context: RenderContext) -> None:
    """Record the reference labels under a verbatim-rendered node as used.

    mdformat writes a ``[label]: url`` definition only when a renderer
    adds its label to ``used_refs``, which the default link and image
    renderers do while descending the inline children. A verbatim face
    skips that descent, so it registers its reference-style links here
    -- otherwise the definition is silently dropped from the output.
    """
    for child in node.walk(include_self=False):
        if (child.type in ('link', 'image')) and child.meta.get('label'):
            context.env['used_refs'].add(child.meta['label'])


def _render_heading(node: RenderTreeNode, context: RenderContext) -> str:
    """Render an ATX heading with its original source face verbatim.

    The default renderer re-escapes the inline content (mangling faces
    like an unbalanced ``*``) and drops an optional closing ``#``
    sequence, so a heading whose source line strips to the bare ATX
    face returns that line instead -- a list-item continuation line
    qualifies. Setext headings and lines carrying container markup
    (blockquote-nested, a heading sharing its list marker's line)
    delegate to the default renderer.
    """
    lines = context.env.get(_SRC_LINES)
    if (lines is not None) and (node.map is not None) and node.markup.startswith('#'):
        line = lines[node.map[0]].strip()
        if (line == node.markup) or line.startswith(node.markup + ' '):
            _register_refs(node, context)
            return line
    return DEFAULT_RENDERERS['heading'](node, context)


def _render_link_row(node: RenderTreeNode, context: RenderContext) -> str:
    """Render an index link row from source, wrapping only where safe.

    The faces render verbatim -- reflowing through the default paragraph
    treatment decodes the escapes away, which oscillates the index
    against ``wiki update`` and can re-parse a desc line as a real
    wikilink. Under a numeric ``--wrap`` the row still honors the column
    width: plain prose lines rewrap greedily with ``[[...]]`` faces
    atomic, while escape-carrying, structure-shaped, and hard-break
    lines keep their breaks (:func:`_wrap_link_row`). The non-numeric
    modes (``keep``, ``no``) stay byte-verbatim like the frontmatter
    face -- stripping even trailing whitespace would delete a hard break
    (two trailing spaces) and trip mdformat's HTML-equivalence check,
    wedging the file.
    """
    _register_refs(node, context)
    lines = context.env.get(_SRC_LINES)
    if (lines is not None) and (node.map is not None):
        region = lines[node.map[0] : node.map[1]]
        wrap_mode = context.options['mdformat'].get('wrap', 'keep')
        if isinstance(wrap_mode, int):
            return _wrap_link_row(region, wrap_mode)
        return '\n'.join(region)
    return node.content


def _wrap_link_row(region: list[str], width: int) -> str:
    """Rewrap a link row's plain prose lines to ``width``, atoms intact.

    The block rule absorbs every contiguous non-blank line regardless of
    content, so a re-broken row still parses back as the same single
    block -- what wrapping must preserve is the *reader's* view: frozen
    lines (:data:`_FROZEN_ROW_LINE` -- escape faces, structure shapes,
    hard-break tails) keep their breaks byte-for-byte, and only maximal
    runs of plain prose lines rejoin and refill greedily. ``[[...]]``
    faces travel as single atoms (the wikilink wrap-atomicity contract),
    and an atom that lands at a fresh line's start but reads as frozen
    structure there rides the previous line instead -- overflow is the
    sanctioned escape for the unbreakable, never a new hazard line. The
    opener line's face-plus-colon prefix counts toward the first line's
    width like any other atom.

    Args:
        region: The row's source lines.
        width: Numeric wrap column.

    Returns:
        The rewrapped row.

    """
    # partition into frozen lines and maximal plain runs; the opener's
    # [[ face is the row itself (never structure), but a hard-break tail
    # freezes it like any other line
    output: list[str] = []
    run: list[str] = []
    for index, line in enumerate(region):
        if index == 0:
            frozen = _HARD_BREAK_TAIL.search(line) is not None
        else:
            frozen = _FROZEN_ROW_LINE.search(line) is not None
        if frozen:
            if run:
                output.extend(_fill_atoms(' '.join(run), width))
                run = []
            output.append(line)
        else:
            run.append(line.strip())
    if run:
        output.extend(_fill_atoms(' '.join(run), width))
    # return the rewrapped row
    return '\n'.join(output)


def _fill_atoms(text: str, width: int) -> list[str]:
    """Greedily fill ``text``'s atoms into lines of at most ``width``.

    A break never creates a load-bearing line the source never had: an
    atom that would open a line as structure (a list marker, a stray
    row face), a bare run left alone on a line (a setext underline), or
    a backslash landing at a line's end (a minted hard break) rides the
    adjacent line instead -- a long line is safe, a new hazard is not.

    Args:
        text: Space-joined plain prose.
        width: Numeric wrap column.

    Returns:
        The filled lines.

    """
    atoms = _ROW_ATOM.findall(text)
    lines: list[str] = []
    current = ''
    for index, atom in enumerate(atoms):
        # fits on the current line (or opens it)
        candidate = f'{current} {atom}' if current else atom
        if (not current) or (len(candidate) <= width):
            current = candidate
            continue
        # breaking here would open a structure-shaped line, strand a
        # bare run alone as the final line, or leave a backslash tail
        # minting a hard break -- overflow instead (marker shapes probe
        # with following text: '- x' is a list, '-- x' is prose)
        run_alone = (index == len(atoms) - 1) and _PURE_RUN.fullmatch(atom)
        if (
            _HAZARD_OPEN.search(f'{atom} x')
            or run_alone
            or current.endswith('\\')
            or _PURE_RUN.fullmatch(current)
        ):
            current = candidate
            continue
        lines.append(current)
        current = atom
    if current:
        lines.append(current)
    return lines


def _render_text(node: RenderTreeNode, context: RenderContext) -> str:
    r"""Render body text, reshaping bracket escapes to the healthy form.

    Real wikilinks are consumed before the default escaper, so the only
    ``[[`` it ever escapes is a non-wikilink -- but its ``\[[``/``\[\[``
    output is byte-identical to the damage a generic formatter does to a
    real wikilink, the signature the wiki's lint scans for. The healthy
    shape keeps the backslash inside the brackets (matching the wiki's
    ``escape_desc``): in a bracket run only the last ``[`` may stay
    escaped. The signature also forms against a following link token
    (``\[`` + ``[face](...)``); the trailing escape is bared there --
    links never nest and every other lone bracket stays escaped, so the
    bare ``[`` is inert (the same next-sibling pattern the default
    renderer uses for a trailing ``!``).
    """
    # render with the default escaper, then reshape bracket-run escapes
    rendered = DEFAULT_RENDERERS['text'](node, context)
    rendered = re.sub(r'\\\[(?=\\?\[)', '[', rendered)
    # bind the trailing-escape clauses
    next_sibling = node.next_sibling
    trailing_escape = rendered.endswith('\\[') and not rendered.endswith('\\\\[')
    next_is_link = (next_sibling is not None) and (next_sibling.type == 'link')
    # bare a trailing escape formed against a following link token
    if trailing_escape and next_is_link:
        rendered = rendered[:-2] + '['
    # return the reshaped text
    return rendered


RENDERERS = {
    'wikilink': _render_wikilink,
    'front_matter': _render_front_matter,
    'hr': _render_hr,
    'heading': _render_heading,
    'link_row': _render_link_row,
    'text': _render_text,
}
