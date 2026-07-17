"""The mdformat parser extension: wiki syntax rules and renderers.

mdformat discovers ``update_mdit`` and ``RENDERERS`` on this module
through the ``mdformat.parser_extension`` entry point declared in
``pyproject.toml``.
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.rules_inline import StateInline
from mdformat.renderer import (
    DEFAULT_RENDERERS,
    WRAP_POINT,
    RenderContext,
    RenderTreeNode,
)
from mdit_py_plugins.front_matter import front_matter_plugin

# env key for the source lines stashed at parse time (see the renderers)
_SRC_LINES = 'mdformat_wiki_src_lines'


def update_mdit(mdit: MarkdownIt) -> None:
    """Register the wiki syntax rules on the markdown-it parser.

    Adds the ``mdit-py-plugins`` front-matter block rule, an atomic
    ``[[...]]`` wikilink inline rule, and a core rule stashing the
    source lines for face-sensitive rendering.

    Args:
        mdit: Parser to extend, one per document mdformat formats.

    """
    mdit.use(front_matter_plugin)
    mdit.inline.ruler.before('link', 'wikilink', _wikilink_rule)
    mdit.core.ruler.push('wiki_stash_src', _stash_src)


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
    src = state.src
    pos = state.pos
    if src[pos : pos + 2] != '[[':
        return False
    end = src.find(']]', pos + 2)
    if end == -1 or '\n' in src[pos + 2 : end]:
        return False
    if not silent:
        token = state.push('wikilink', '', 0)
        token.content = src[pos + 2 : end]
    state.pos = end + 2
    return True


def _render_wikilink(node: RenderTreeNode, context: RenderContext) -> str:
    """Render a wikilink back to its literal ``[[...]]`` face."""
    return f'[[{node.content}]]'


def _render_front_matter(node: RenderTreeNode, context: RenderContext) -> str:
    """Render frontmatter byte-verbatim, fences and content untouched."""
    lines = context.env.get(_SRC_LINES)
    if lines is not None and node.map is not None:
        region = lines[node.map[0] : node.map[1]]
        return '\n'.join(region)
    return f'---\n{node.content}\n---'


def _render_hr(node: RenderTreeNode, context: RenderContext) -> str:
    """Render a thematic break, preserving only the literal ``***`` face."""
    lines = context.env.get(_SRC_LINES)
    if lines is not None and node.map is not None:
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
    if lines is not None and node.map is not None and node.markup.startswith('#'):
        line = lines[node.map[0]].strip()
        if line == node.markup or line.startswith(node.markup + ' '):
            return line
    return DEFAULT_RENDERERS['heading'](node, context)


def _in_block(block_name: str, node: RenderTreeNode) -> bool:
    """Whether ``node`` sits inside a block of the given type."""
    while node.parent:
        if node.parent.type == block_name:
            return True
        node = node.parent
    return False


def _is_link_row(inline: RenderTreeNode) -> bool:
    """Whether an inline node opens an index link row (``[[t|l]]: ...``)."""
    children = inline.children or ()
    return (
        len(children) >= 2
        and children[0].type == 'wikilink'
        and children[1].type == 'text'
        and children[1].content.startswith(':')
    )


def _render_text(node: RenderTreeNode, context: RenderContext) -> str:
    """Render an index link-row desc face-verbatim, wrapping but not escaping.

    A link row's desc parses as ordinary inline text, so the default renderer
    escapes a bare ``*`` or ``_`` (``**kwargs``, ``_verb``) that the page's
    frontmatter desc holds unescaped -- the escape diverges the row from its
    source, and the wiki tool then overwrites it back, so the two fight every
    run. Descs are plain prose: a desc token renders as-is, only wrap points
    go in. All other text keeps the default escaping.
    """
    inline = node.parent
    if inline is not None and inline.type == 'inline' and _is_link_row(inline):
        text = node.content
        if context.do_wrap and _in_block('paragraph', node):
            text = re.sub(r'[ \t\n]+', WRAP_POINT, text)
        return text
    return DEFAULT_RENDERERS['text'](node, context)


RENDERERS = {
    'wikilink': _render_wikilink,
    'front_matter': _render_front_matter,
    'hr': _render_hr,
    'heading': _render_heading,
    'text': _render_text,
}
