.. _background:

Background
==========

Conceptually, Malloovia is an extension of `Lloovia <https://github.com/asi-uniovi/lloovia>`_, to allow for multiple applications, each one with a different workload and performance, and it is described in a paper to be published in september 2017.

However, the implementation of Malloovia is not a simple extension of the one of Lloovia. Instead, the code was completly rewritten to obtain a more clean, robust and maintenable implementation. Malloovia is a standard python package which can be installed with `pip` and has very few dependencies (which are automatically installed if you ``pip install malloovia``):

* `PuLP <https://pythonhosted.org/PuLP/>`_ is used to create and solve the linear programming problem.
* `PyYaml <https://pypi.python.org/pypi/PyYAML>`_ is used to allow Malloovia to read the problem definition from YAML files, and write the solution to other YAML files, for better interoperability with other tools.
* `jsonschema <https://pypi.python.org/pypi/jsonschema>`_ is used to validate the syntax of the YAML files used.

This small number of requirements is an advantage over Lloovia which had dependencies on other "heavy" packages, such as numpy, pandas, matplotlib, jupyter notebooks, etc.

The reason for the small number of dependencies is that Malloovia is more focused. It does not provides tools for analyzing, inspecting or displaying the solution, but only for obtaining it. Since the solution can be stored in the standard YAML format, it can be read, analyzed and displayed it using other tools and libraries, not neccessarily python based.

.. warning::
   This documentation is still in progress.


The system model
----------------

The solving method
------------------

The solution
------------

