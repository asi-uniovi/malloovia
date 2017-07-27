.. malloovia documentation master file, created by
   sphinx-quickstart on Fri Jul 21 10:09:42 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Malloovia
=================================

Release v\ |version|. (:ref:`Installation <install>`)

.. Commented out
    .. image:: https://img.shields.io/pypi/v/malloovia.svg
            :target: https://pypi.python.org/pypi/malloovia

    .. image:: https://img.shields.io/travis/jldiaz-uniovi/malloovia.svg
            :target: https://travis-ci.org/jldiaz-uniovi/malloovia

    .. image:: https://readthedocs.org/projects/malloovia/badge/?version=latest
            :target: https://malloovia.readthedocs.io/en/latest/?badge=latest
            :alt: Documentation Status

    .. image:: https://pyup.io/repos/github/jldiaz-uniovi/malloovia/shield.svg
         :target: https://pyup.io/repos/github/jldiaz-uniovi/malloovia/
         :alt: Updates


Use linear programming to allocate applications to cloud infrastructure.

::

        >>> from malloovia import *
        >>> problem = read_problems_from_github(dataset="problem1", id="example")
        >>> phase_i_solution = PhaseI(problem).solve()
        >>> phase_i_solution.solving_stats.optimal_cost
        178.0
        >>> phase_i_solution.allocation._inspect()
        AllocationInfo:
          apps: (App('app0'), App('app1'))
          instance_classes: (InstanceClass('m3large_r'), InstanceClass('m3large'))
          workload_tuples: [(30, 1003), (32, 1200), (30, 1194)]
          values: [[[3.0, 0.0], [3.0, 0.0]], [[3.0, 1.0], [3.0, 0.0]], [[3.0, 0.0], [3.0, 0.0]]]
          units: 'vms'
          repeats: [2, 1, 1]

See :ref:`background` for details about the problem that Malloovia is solving.
See :ref:`usage` for details about the high-level Malloovia API, and :ref:`Documentation for developers <developers>` for details about the implementation.

* Free software: MIT license

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   background
   install
   usage
   developers
   contributing
   authors
   history
