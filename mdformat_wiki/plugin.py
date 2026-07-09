"""The mdformat parser extension: wiki syntax rules and renderers.

mdformat discovers ``update_mdit`` and ``RENDERERS`` on this module
through the ``mdformat.parser_extension`` entry point declared in
``pyproject.toml``.
"""

from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.rules_inline import StateInline
from mdformat.renderer import DEFAULT_RENDERERS, RenderContext, RenderTreeNode
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


RENDERERS = {
    'wikilink': _render_wikilink,
    'front_matter': _render_front_matter,
    'hr': _render_hr,
}
