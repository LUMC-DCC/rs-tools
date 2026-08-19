"""Sphinx configuration.

The prose is Markdown so it stays readable on GitHub; MyST renders the same
files here without a second source format. The API reference comes from the
docstrings, so nothing is written twice.

Build it from the backend project, which owns the dependencies::

    cd backend
    poetry install --with docs
    poetry run sphinx-build -b html -W --keep-going ../docs ../docs/_build/html
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(DOCS_ROOT / "_ext"))
sys.path.insert(0, str(DOCS_ROOT.parents[0] / "backend" / "src"))

from rs_tools import __version__  # noqa: E402

project = "Research Software Tools"
author = "Mariia Steeghs-Turchina"
copyright = f"{date.today().year}, Leiden University Medical Center"
release = __version__
version = __version__

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",
    "rs_tools_docs",
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build"]

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3
# Mermaid diagrams are written as ```mermaid fences, which GitHub renders
# natively. This makes Sphinx render the same source.
myst_fence_as_directive = ["mermaid"]

autodoc_typehints = "description"
autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "undoc-members": False}
# The application factory builds a Redis client at import time, and autodoc
# imports every documented module. Nothing here is called during a docs build,
# so importing is enough, but the entry point module is documented from its
# factory rather than its module-level `app`.
napoleon_numpy_docstring = True
napoleon_google_docstring = False
# Render an "Attributes" section as field-list entries on the class rather than
# as separate object descriptions. Autodoc already emits an entry per dataclass
# and pydantic field, and without this every documented attribute is described
# twice.
napoleon_use_ivar = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "fastapi": ("https://fastapi.tiangolo.com", None),
}

html_theme = "sphinx_book_theme"
html_title = f"{project} {release}"
html_static_path: list[str] = []
html_theme_options = {
    "repository_url": "https://github.com/LUMC-DCC/rs-tools",
    "repository_branch": "main",
    "path_to_docs": "docs",
    "use_repository_button": True,
    "use_issues_button": True,
    "use_edit_page_button": True,
    "use_source_button": True,
    "home_page_in_toc": True,
    "show_toc_level": 2,
    "navigation_with_keys": False,
}
