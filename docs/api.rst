.. _api:

API
===

System definition
-------------------------

The System is defined from the :class:`.InstanceClass`\ es which compose it.
Instance classes belong to :class:`.LimitingSet`\ s, and have different :class:`.PerformanceValues` for different :class:`.App`\ s.
To allow for different scenarios, the same system could have different performance values, and these are identified as :class:`.PerformanceSet`\ s.

.. autoclass:: malloovia.LimitingSet
    :members:

.. autoclass:: malloovia.InstanceClass
    :members:

.. autoclass:: malloovia.App
    :members:

.. autoclass:: malloovia.PerformanceValues
    :members:

.. autoclass:: malloovia.PerformanceSet
    :members:

Problem definition
---------------------------

The :class:`.Problem` is defined by the system components (instance classes and performances), plus a :class:`.Workload` prediction.
A :class:`.System` is a :class:`.Problem` without the workloads. Utility function :func:`.system_from_problem` can be used to extract the system from a problem.


.. autoclass:: malloovia.Workload
    :members:

.. autoclass:: malloovia.Problem
    :members:

.. autoclass:: malloovia.System
    :members:

.. autofunction:: malloovia.system_from_problem

Solving
------------

The solver operates in two phases. 

* :class:`.PhaseI` solves the whole reservation period and provides a :class:`.SolutionI` object, which contains :class:`.SolvingStats`,
  :class:`.MallooviaStats`, the optimal :class:`.AllocationInfo` for each possible load-level, and the :class:`ReservedAllocation` useful for the next phase.

* :class:`.PhaseII` allows to solve single timeslots, or to perform a simulation of a complete reservation period, by solving separately each timeslot. 
  It provides a :class:`.SolutionII` as result, which contains :class:`.GlobalSolvingStats` which aggregates statistics about all solved timeslots, and the :class:`.AllocationInfo` with the optimal allocation for each timeslot.
  Optionally it can accept a :class:`.STWPredictor` from which it obtains the short-term workload prediction of each timeslot.
  An example of such a predictor is :class:`.OmniscientSTWPredictor`.

.. autoclass:: malloovia.PhaseI
    :members:

.. autoclass:: malloovia.ReservedAllocation
    :members:

.. autoclass:: malloovia.PhaseII
    :members:

.. autoclass:: malloovia.PhaseIIGuided
    :members:

Solutions
----------

.. autoclass:: malloovia.SolutionI
    :members:

.. autoclass:: malloovia.SolvingStats
    :members:

.. autoclass:: malloovia.MallooviaStats
    :members:

.. autoclass:: malloovia.Status
    :members:

.. autoclass:: malloovia.AllocationInfo
    :members:

.. autoclass:: malloovia.SolutionII
    :members:

.. autoclass:: malloovia.GlobalSolvingStats
    :members:

.. autoclass:: malloovia.STWPredictor
    :members:

.. autoclass:: malloovia.OmniscientSTWPredictor
    :members:

Internal solver
-----------------

Phase I and II make use of :class:`.MallooviaLp` class, which is the core of the solver.
Although using this class is not usually required, it is exposed because it can be useful to inherit from it to implement other LP constraints.
Also, phase II makes use of :class:`.MallooviaLpMaximizeTimeslotPerformance` for the timeslots in which the demanded performance cannot be achieved without breaking the limits.

.. autoclass:: malloovia.MallooviaLp
    :members:

.. autoclass:: malloovia.MallooviaLpMaximizeTimeslotPerformance
    :members:

Input/Output and utility functions
----------------------------------

.. autofunction:: malloovia.read_problems_from_yaml

.. autofunction:: malloovia.read_problems_from_github


.. autofunction:: malloovia.problems_to_yaml

.. autofunction:: malloovia.solutions_to_yaml


.. autofunction:: malloovia.check_valid_problem


.. autofunction:: malloovia.compute_allocation_cost

.. autofunction:: malloovia.compute_allocation_performance

.. autofunction:: malloovia.get_load_hist_from_load

.. autofunction:: malloovia.allocation_info_as_dicts


