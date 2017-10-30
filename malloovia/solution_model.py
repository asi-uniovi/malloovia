# coding: utf-8

"""Classes for storing and reporting solutions of malloovia problems."""

from typing import Union
from enum import IntEnum
from functools import singledispatch
import pulp

from .model import (
    _namedtuple_with_defaults, PerformanceSet
)

class Status(IntEnum):
    "Possible status of malloovia's solution"
    unsolved = 0
    optimal = 1
    infeasible = 2
    integer_infeasible = 3
    overfull = 4
    trivial = 5
    aborted = 6
    cbc_error = 7
    unknown = 8


def pulp_to_malloovia_status(status: int) -> Status:
    """Receives a PuLP status code and returns a Malloovia :class:`Status`."""
    if status == pulp.LpStatusInfeasible:
        status = Status.infeasible
    elif status == pulp.LpStatusNotSolved:
        status = Status.aborted
    elif status == pulp.LpStatusOptimal:
        status = Status.optimal
    elif status == pulp.LpStatusUndefined:
        status = Status.integer_infeasible
    else:
        status = Status.unknown
    return status


class MallooviaHistogram(dict):
    """This class stores a multi-dimensional histogram, providing the same
    interface than a standard dict whose keys are workload tuples and the
    values are the count of the number of times that the tuple is observed
    in the computed period."""

    apps = None
    """The apps attribute stores a tuple with references to the apps involved
    in the workload. The order of this tuple must match the order of workloads for
    of each tuple which acts as key in the histogram"""

    def __missing__(self, key):
        # Default value for missing keys is zero
        return 0

    def __repr__(self):
        return "MallooviaHistogram with %d values" % len(self)


# pylint doesn't like namedtuples, because their appear as variables
# but the name is class-like
# pylint: disable=invalid-name
MallooviaStats = _namedtuple_with_defaults(
    "MallooviaStats",
    ['gcd', 'status'],
    gcd_multiplier=1.0,
    frac_gap=None,
    max_seconds=None,
    lower_bound=None
)
"""Stores data related to the Malloovia solver."""
MallooviaStats.gcd.__doc__ = "bool: whether GCD technique was used or not."
MallooviaStats.status.__doc__ = ":class:`Status`: status of the solution."
MallooviaStats.gcd_multiplier.__doc__ = """\
    float: the multiplier used in GCD technique (defaults to 1)."""
MallooviaStats.frac_gap.__doc__ = """\
    float: the fracGap passed to cbc solver (defaults to None)."""
MallooviaStats.max_seconds.__doc__ = """\
    float: the maxSeconds passed to cbc solver (defaults to None)."""
MallooviaStats.lower_bound.__doc__ = """\
    float: the lower bound of the solution as reported by cbc when the
        optimal solution is not available (defaults to None)."""

SolvingStats = _namedtuple_with_defaults(
    "SolvingStats",
    ["algorithm",
     "creation_time", "solving_time",
     "optimal_cost"
    ])
"""Stores the statistics that can be gathered from a solution
of Phase I, or one single timeslot in Phase II."""
SolvingStats.algorithm.__doc__ = """\
    :class:`MallooviaStats`: additional info related to the particular
        algorithm used to solve the problem."""
SolvingStats.creation_time.__doc__ = """\
    float: time required to create the LP problem."""
SolvingStats.solving_time.__doc__ = """\
    float: time required to solve the LP problem."""
SolvingStats.optimal_cost.__doc__ = """\
    float: optimal cost as reported by the LP solver."""

GlobalSolvingStats = _namedtuple_with_defaults(
    "GlobalSolvingStats",
    ["creation_time", "solving_time", "optimal_cost", "status"],
    default_algorithm=None
    )
"""Stores the global statistics for Phase II, which are a sum of the
statistics of each timeslot."""
GlobalSolvingStats.creation_time.__doc__ = """\
    float: sum of the time required to create the LP problem
        for each timeslot."""
GlobalSolvingStats.solving_time.__doc__ = """\
    float: sum of the time required to solve the LP problem
        for each timeslot."""
GlobalSolvingStats.optimal_cost.__doc__ = """\
    float: sum of the optimal costs as reported by the LP problem
        for each timeslot."""
GlobalSolvingStats.status.__doc__ = """\
    :class:`Status`: global status computed from the status of
        each timeslot."""

ReservedAllocation = _namedtuple_with_defaults(
    "ReservedAllocation",
    ["instance_classes", "vms_number"]
)
"""Stores the number of reserved instances to allocate during the whole reservation
period."""
ReservedAllocation.instance_classes.__doc__ = """\
    List[:class:`InstanceClass`]: list of reserved instance classes
        in the allocation."""
ReservedAllocation.vms_number.__doc__ = """\
    List[float]: list of numbers, representing the number of instance classes
        to be reserved of each type. The corresponding instance class is obtained
        from the ``instance_classes`` attribute using the same index."""


AllocationInfo = _namedtuple_with_defaults(
    "AllocationInfo",
    ["apps", "instance_classes", "workload_tuples", "values", "units"],
    repeats=[]
)
"""Stores the allocation for a series of timeslots. It can be a single
timeslot, or the sequence of allocations for the whole reservation period."""
AllocationInfo.values.__doc__ = """\
     Sequence[Sequence[Sequence[float]]]: contains a list with one element
        per timeslot. Each element in this sequence is a list (with one element
        per app), which is in turn a list (with one element per instance class).
        These values are numbers which can represent the number of instance
        classes of that type to be allocated for that app during that timeslot,
        or the cost associated with these instance classes, or the performance
        given by these instance classes, depending on the ``units`` field.
        So, for example, if ``units`` is ``"vms"``, then ``values[2][1][3]``
        represents the number of VMs of the instance class 3 to be allocated
        for application 1 during the timseslot 2.

        Note that, if the allocation contains a single timeslot, it is still
        necessary to specify the index (0) in the first dimension,
        e.g. ``vms_number[0][1][3]``.

        To match the indexes in those arrays to actual instance classes and
        apps, the attributes ``instance_classes`` and ``apps`` should be used.
        So, for the above example, the application would be ``apps[1]`` and
        the instance class would be ``instance_classes[3]``. If required,
        the workload for that particular timeslot (2) can also be retrieved from
        ``workload_tuples[2]``."""
AllocationInfo.units.__doc__ = """\
    str: a string identifying the kind of information stored in the ``values``
        field. It can be ``"vms"`` (number of VM instances), ``"cost"`` or any
        currency (cost of these instances) or ``"rph"`` (performance of these
        instances)."""
AllocationInfo.apps.__doc__ = """\
    Sequence[:class:`App`]: is a list of apps to give meaning to the second
        index in ``values``."""
AllocationInfo.instance_classes.__doc__ = """\
    Sequence[:class:`InstanceClass`]: is a list of instance classes to give
        meaning to the third index in ``values``."""
AllocationInfo.workload_tuples.__doc__ = """\
    Sequence[Tuple[float]]: is a list of workload tuples to give meaning to the
        first index in ``values``. Each element is a tuple with as many values
        as apps, being each one the workload for each app."""


SolutionI = _namedtuple_with_defaults(
    "SolutionI",
    ["id", "problem", "solving_stats", "allocation", "reserved_allocation"],
)
"""Stores a solution for phase I."""
SolutionI.id.__doc__ = "str: arbitrary id for this object."
SolutionI.problem.__doc__ = """\
    :class:`Problem`: reference to the problem which originated this solution."""
SolutionI.solving_stats.__doc__ = """\
    :class:`SolvingStats`: statistics about this solution."""
SolutionI.allocation.__doc__ = """\
    :class:`AllocationInfo`: allocation provided in this solution."""
SolutionI.reserved_allocation.__doc__ = """\
    :class:`ReservedAllocation`: allocation for reserved instances only."""

SolutionII = _namedtuple_with_defaults(
    "SolutionII",
    ["id", "problem", "solving_stats", "global_solving_stats",
     "previous_phase", "allocation"],
)
"""Stores a solution for phase II."""
SolutionII.id.__doc__ = "str: arbitrary id for this object."
SolutionII.problem.__doc__ = """\
    :class:`Problem`: reference to the problem which originated this solution."""
SolutionII.solving_stats.__doc__ = """\
    :Sequence[class:`SolvingStats`]: list of the SolvingStats for
        each timeslot."""
SolutionII.global_solving_stats.__doc__ = """\
    :class:`GlobalSolvingStats`: summary of the solving stats."""
SolutionII.previous_phase.__doc__ = """\
    :class:`SolutionI`: reference to the solution of the previous phase."""
SolutionII.allocation.__doc__ = """\
    :class:`AllocationInfo`: allocation for the whole period, built from the
        allocations of the individual timeslots."""

@singledispatch
def compute_allocation_cost(alloc: AllocationInfo) -> AllocationInfo:
    """Computes the cost of each element of the allocation.

    Args:
        alloc: the allocation whose cost has to be computed

    Returns:
        Another allocation in which the ``values`` field contains
        the cost of that element (it is the original ``values``
        multiplied by the cost of the corresponding instance class)
    """
    costs = []
    for row in alloc.values:
        costs_row = []
        for app_alloc in row:
            costs_app = []
            for i, _ in enumerate(app_alloc):
                costs_app.append(app_alloc[i] * alloc.instance_classes[i].price)
            costs_row.append(costs_app)
        costs.append(costs_row)

    return alloc._replace(values=costs, units="cost")

@compute_allocation_cost.register(SolutionI)
@compute_allocation_cost.register(SolutionII)
def _(solution: Union[SolutionI, SolutionII]) -> AllocationInfo:
    return compute_allocation_cost(solution.allocation)

@singledispatch
def compute_allocation_performance(
        alloc: AllocationInfo,
        performances: PerformanceSet) -> AllocationInfo:
    """Computes the performance of each element of the allocation.

    Args:
        alloc: the allocation whose performance has to be computed
        performances: the set of performances for each pair of instance class
            and application

    Returns:
        Another allocation in which the ``values`` field contains
        the performance of that element (it is the original ``values``
        multiplied by the performance of the corresponding instance class
        for the corresponding app)
    """
    perfs = []
    for row in alloc.values:
        perfs_row = []
        for j, app_alloc in enumerate(row):
            app = alloc.apps[j]
            perfs_app = []
            for i, _ in enumerate(app_alloc):
                iclass = alloc.instance_classes[i]
                perfs_app.append(
                    app_alloc[i] * performances[iclass, app])
            perfs_row.append(perfs_app)
        perfs.append(perfs_row)
    return alloc._replace(values=perfs, units="rph")

@compute_allocation_performance.register(SolutionI)
@compute_allocation_performance.register(SolutionII)
def _(solution: Union[SolutionI, SolutionII]) -> AllocationInfo: # pylint:disable=function-redefined
    return compute_allocation_performance(
        solution.allocation,
        solution.problem.performances.values)

__all__ = [
    'Status', 'MallooviaStats', 'SolvingStats', 'GlobalSolvingStats',
    'AllocationInfo', 'ReservedAllocation', 'SolutionI', 'SolutionII',
    'compute_allocation_cost', 'compute_allocation_performance'
]
