"""The ``mdformat_wiki`` package.

Mdformat plugin preserving wikilinks, frontmatter, and index delimiter.
"""

from . import cli, core, util
from .cli import *
from .core import *
from .util import *

__version__ = '0.0.0'
