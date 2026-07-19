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


def update_mdit(mdit: MarkdownIt) -> None:
    """Register the wiki syntax rules on the markdown-it parser.

    Adds a front-matter block rule matching the wiki reader's fence
    grammar, an atomic ``[[...]]`` wikilink inline rule, and core rules
    normalizing a leading BOM and stashing the source lines for
    face-sensitive rendering.

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

    The opener is line 0 stripping to exactly ``---``; only an
    unindented line stripping to ``---`` closes the block. An indented
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
    # opener: line 0 only, stripping to exactly ---
    if start_line != 0:
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
            return line
    return DEFAULT_RENDERERS['heading'](node, context)


def _is_link_row(inline: RenderTreeNode, /) -> bool:
    """Return whether an inline node opens an index link row (``[[t|l]]: ...``).

    Mirrors the wiki reader's row grammar: the label pipe is mandatory,
    so a body paragraph opening with a bare ``[[target]]`` is prose.
    """
    children = inline.children or ()
    if len(children) < 2:
        return False
    labeled_link = (children[0].type == 'wikilink') and ('|' in children[0].content)
    colon_text = (children[1].type == 'text') and children[1].content.startswith(':')
    return labeled_link and colon_text


def _render_paragraph(node: RenderTreeNode, context: RenderContext) -> str:
    r"""Render an index link-row paragraph verbatim, escapes and lines intact.

    A link block is structured data: the ``[[t|l]]`` faces, the
    ``escape_desc`` backslashes on continuation lines (``\***``/``[\[``),
    and the line breaks all round-trip unchanged, so the wiki reader
    reads back exactly what it wrote and the index converges. Reflowing
    prose (the default) decodes the escapes away, which oscillates the
    index and can re-parse a desc line as a real wikilink. Rendered from
    source like the frontmatter/``***`` faces. Only a top-level
    paragraph qualifies: a container re-prefixes its rendered lines
    (``> ``), which would double on a verbatim slice.
    """
    # read the stashed source lines and the opening inline node
    lines = context.env.get(_SRC_LINES)
    inline = node.children[0] if node.children else None
    # bind the link-block qualification clauses
    has_source = (lines is not None) and (node.map is not None)
    top_level = (node.parent is not None) and (node.parent.type == 'root')
    has_inline = (inline is not None) and (inline.type == 'inline')
    # render a qualifying link block verbatim from source
    if has_source and top_level and has_inline and _is_link_row(inline):
        region = lines[node.map[0] : node.map[1]]
        return '\n'.join(line.rstrip() for line in region)
    # return the default rendering
    return DEFAULT_RENDERERS['paragraph'](node, context)


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
    'paragraph': _render_paragraph,
    'text': _render_text,
}
