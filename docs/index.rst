.. malloovia documentation master file, created by
   sphinx-quickstart on Fri Jul 21 10:09:42 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Malloovia
=================================

Release v\ |version|. (:ref:`Installation <install>`)

Use linear programming to allocate applications to cloud infrastructure.

.. doctest::

        >>> from malloovia import *
        >>> problem = read_problems_from_github(dataset="problem1", _id="example")
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
See :ref:`usage` for details about the python and YAML interfaces, and :ref:`API documentation <api>` for details about the implementation.

* Free software: MIT license

.. toctree::
   :maxdepth: 2
   :hidden:

   install
   background
   usage
   api
   cli
   yaml
   contributing
   about