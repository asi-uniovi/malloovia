.. _install:
.. highlight:: bash

============
Installation
============


Python version
--------------

Malloovia requires Python (at least version 3.5) to work. If you don't have Python installed,
or have a different version an easy way to get python 3.6 for different platforms
is to install `anaconda <https://www.continuum.io/downloads>`_ or
`miniconda <http://conda.pydata.org/miniconda.html>`_.

Ensure that you have the correct version::

  $ python --version
  Python 3.6.1 :: Continuum Analytics, Inc.

Although the message after the ``::`` can be different in your system, the version should be
at least ``3.5.0``. If you get ``2.7.*`` instead, try again using ``python3`` command instead
of ``python``. In the remaining of this section we will write ``python``, but you have to write
``python3`` if your system defaults to version 2.7.


Virtual environment
--------------------

It is highly recommended that you create a virtual environment to install any python package, so
that it does not interfere with other preinstalled packages or python versions.

Although there are several ways to achieve this, Python 3 comes with its own virtual environment
manager, and thus it is the only way we will document here. Refer to `conda virtual environments
<https://conda.io/docs/using/envs.html>`_, if you prefer to use the virtual environment manager
which comes with Anaconda, or to `virtualenv documentation <https://virtualenv.pypa.io/en/stable/>`_
if you prefer to use the ``virtualenv`` command.

Using only python, you create a virtual environment by typing (unix based platforms)::

  $ python -m venv ~/myenvs/malloovia

Or, in windows with the standard command line (PowerShell would require modifications not explained here):

.. code-block:: doscon

  C:\> python -m venv %USERPROFILE%\myenvs\malloovia

This will create the folder ``myenvs/malloovia`` in the home folder, with a private copy of Python and
other tools (like ``pip``) required to install packages locally into that folder.

To use that installation of python instead of the global one, you have to "activate" the environment.
That consists in executing a script called ``activate`` located in that folder.

In unix based platforms (Linux or OSX), type::

  $ source ~/myenvs/malloovia/bin/activate

In Windows:

.. code-block:: doscon

  C:\> %USERPROFILE%\myenvs\malloovia\Scripts\activate

This will modify the ``PATH`` to use that environment (and it will change your prompt as a reminder).
From now on, all packages installed with `pip <https://pip.pypa.io>`_ will be installed in.
``~/myenvs/malloovia/`` and do not interfere with your global python installation. If you
want to leave the environment and return to your global installation, use (both Unix and Windows)::

  $ deactivate

Also remember that the environment is active only while you don't close the terminal. You have to
activate the environment for each terminal you open.



Malloovia package
-------------------------------------

To install malloovia in the virtual environment, if it is active (both Unix and Windows)::

  (malloovia)$ pip install malloovia

This will also install other packages that are required by Malloovia.



Linear programming solver
---------------------------------------------

Malloovia uses `PuLP <https://pythonhosted.org/PuLP/>`_ as Linear Programming modeling language
and as interface to several solvers. It is a python library which is installed as part of the
installation above. PuLP allows the creation of files describing the problem
(using .lp or .mps formats) from Python, and provides a consistent interface with different
solvers, but it is not itself a solver.

Although PuLP includes a binary executable with ``cbc`` solver, which is used by default
if no other solver is specified, in order to gain more flexibility in the number of options
which can be passed to the solver, a working installation of
`COIN-OR <https://projects.coin-or.org/Cbc>`_ cbc solver is needed.

In debian based distributions of Linux (e.g.: ubuntu) it is easy to get::

   $ sudo apt-get install coinor-cbc

For windows, or other platforms, refer to the `Download and install
<https://projects.coin-or.org/Cbc#DownloadandInstall>`_ instructions in COIN-OR site.


Source code
-----------------------

The source code of Malloovia is `available on Github <https://github.com/asi-uniovi/malloovia>`_,
as well as the tests and the source of this documentation.
You don't need it unless you are interested in :ref:`contributing <contributing>`.
