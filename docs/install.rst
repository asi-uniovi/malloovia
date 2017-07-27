.. _install:
.. highlight:: shell


Installation
============

Setup
-----

Malloovia requires Python 3 to work. If you don't have Python installed, an easy way to get it
is to install `conda <https://www.continuum.io/downloads>`_ or.
`miniconda <http://conda.pydata.org/miniconda.html>`_.

It is highly recommended that you create a virtual environment to install any python package.
Although anaconda has his own way to create environments, you can also use the standard python way,
which for python 3 is::

  $ python3 -m venv ~/myenvs/malloovia

This will create the folder ``~/myenvs/malloovia`` with a private copy of python3 and
other tools required to install packages locally into that folder.

Activate the environment::

  $ source ~/myenvs/malloovia/bin/activate
  (malloovia)$ which python
  ~/myenvs/malloovia/bin/python

and this will set the PATH to use that environment (and change your prompt as a reminder). From
now on, all packages installed with `pip <https://pip.pypa.io>`_ will be installed in.
``~/myenvs/malloovia/`` and do not interfere with your global python installation. If you
want to leave the environment and return to your global installation, use::

  $ deactivate

Installation of the malloovia package
-------------------------------------

To install malloovia (in the virtual environment if it is active)::

  $ pip install malloovia

This will also install other packages that are required by Malloovia.

Installation of the linear programming solver
---------------------------------------------

Mallovia uses `PuLP <https://pythonhosted.org/PuLP/>`_ as Linear Programming modelling language
and as an interface to several solvers. It is a python library which is installed as part of the
installation above. PuLP allows the creation of files describing the problem
(using .lp or .mps formats) from Python, and provides a consistent interface with different
solvers, but it is not itself a solver.

Although PuLP includes a binary executable with ``cbc`` solver, which is used by default
if no other solver is specified, in order to gain more flexibility in the number of options
which can be passed to the solver, a working installation of
`COIN-OR <https://projects.coin-or.org/Cbc>`_ cbc solver is needed.

In debian based distributions of Linux (e.g.: ubuntu) it is easy to get::

   $ sudo apt-get install coinor-cbc

The version of ``cbc`` used by the authors is ``2.8.12``

Getting the Source Code
-----------------------

The source code of Malloovia is `available on Github <https://github.com/asi-uniovi/malloovia>`_,
as well as the tests and the source of this documentation.
You don't need it unless you are interested in :ref:`contributing <contributing>`.
