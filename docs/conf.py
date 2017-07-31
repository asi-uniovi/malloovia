#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Malloovia documentation build configuration file, created by
# sphinx-quickstart on Fri Jul 21 10:09:42 2017.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
# sys.path.insert(0, '/home/jldiaz/Dropbox/Investigacion/Cloud/repositorios/malloovia/model')
sys.path.insert(0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
)

import malloovia  # To get the version
from malloovia import * # To get the high level api

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinx.ext.autodoc',
              'sphinxcontrib.napoleon',
              'sphinx_autodoc_typehints',
              'sphinx.ext.doctest',
              'sphinx.ext.viewcode']
autoclass_content = 'both'
doctest_test_doctest_blocks = ''
doctest_global_setup = "from malloovia import *"

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'malloovia'
copyright = '2017, ASI Uniovi'
author = 'ASI Uniovi'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = malloovia.__version__   # Get malloovia's version
# The full version, including alpha/beta/rc tags.
release = ''

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#

html_theme = 'alabaster'

html_theme_options = {
        'page_width': "1008px",
        'logo': 'malloovia_logo.png',
        'logo_name': True,
        'description': 'Use linear programming to allocate applications to cloud infrastructure',
        'fixed_sidebar': True,
        'show_related': True,
        'show_powered_by': False,
        'sidebar_collapse': True,
        # 'github_user': 'asi-uniovi',
        # 'github_repo': 'malloovia',
        # 'travis_button': True,
        }
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'searchbox.html',
    ]
}

html_static_path = ['_static']
html_favicon = "_static/malloovia.ico"

# html_sidebars = {
#         '**': ['globaltoc.html', 'relations.html',
#                'sourcelink.html', 'searchbox.html', 'better.html']
#         }

# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'mallooviadoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',

    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'malloovia.tex', 'Malloovia Documentation',
     'ASI Uniovi', 'manual'),
]


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'malloovia', 'Malloovia Documentation',
     [author], 1)
]


# -- Options for Texinfo output -------------------------------------------

# Grouping the ocument tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'malloovia', 'Malloovia Documentation',
     author, 'malloovia', 'Use linear programming to allocate applications to cloud infrastructure.',
     'Miscellaneous'),
]



# -- Options for Epub output ----------------------------------------------

# Bibliographic Dublin Core info.
epub_title = project
epub_author = author
epub_publisher = author
epub_copyright = copyright

# The unique identifier of the text. This can be a ISBN number
# or the project homepage.
#
# epub_identifier = ''

# A unique identification for the text.
#
# epub_uid = ''

# A list of files that should not be packed into the epub file.
epub_exclude_files = ['search.html']


