# coding: utf-8

"""Classes for storing and reporting solutions of malloovia problems."""

from typing import Union, NamedTuple, Optional, List, Sequence, Tuple
from enum import IntEnum
from functools import singledispatch
import pulp  # type: ignore

from .model import (
    remove_namedtuple_defaultdoc,
    PerformanceValues,
    InstanceClass,
    App,
    Problem,
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
        r = Status.infeasible
    elif status == pulp.LpStatusNotSolved:
        r = Status.aborted
    elif status == pulp.LpStatusOptimal:
        r = Status.optimal
    elif status == pulp.LpStatusUndefined:
        r = Status.integer_infeasible
    else:
        r = Status.unknown
    return r


class MallooviaHistogram(dict):
    """This class stores a multi-dimensional histogram, providing the same
    interface than a standard dict whose keys are workload tuples and the
    values are the count of the number of times that the tuple is observed
    in the computed period."""

    apps: Tuple[App, ...] = None
    """The apps attribute stores a tuple with references to the apps involved
    in the workload. The order of this tuple must match the order of workloads for
    of each tuple which acts as key in the histogram"""

    def __missing__(self, key):
        # Default value for missing keys is zero
        return 0

    def __repr__(self):
        return "MallooviaHistogram with %d values" % len(self)


@remove_namedtuple_defaultdoc
class MallooviaStats(NamedTuple):
    """Stores data related to the Malloovia solver."""

    gcd: bool
    "bool: whether GCD technique was used or not."

    status: Status
    ":class:`.Status`: status of the solution."

    gcd_multiplier: float = 1.0
    """float: the multiplier used in GCD technique (defaults to 1.0)."""

    frac_gap: Optional[float] = None
    """float: the fracGap passed to cbc solver (defaults to None)."""

    max_seconds: Optional[float] = None
    """float: the maxSeconds passed to cbc solver (defaults to None)."""

    lower_bound: Optional[float] = None
    """float: the lower bound of the solution as reported by cbc when the
            optimal solution is not available (defaults to None)."""


@remove_namedtuple_defaultdoc
class SolvingStats(NamedTuple):
    """Stores the statistics that can be gathered from a solution
    of Phase I, or one single timeslot in Phase II."""

    algorithm: MallooviaStats
    """:class:`.MallooviaStats`: additional info related to the particular
        algorithm used to solve the problem."""

    creation_time: float
    """float: time required to create the LP problem."""

    solving_time: float
    """float: time required to solve the LP problem."""

    optimal_cost: float
    """float: optimal cost as reported by the LP solver, or None if no solution
           was found."""


@remove_namedtuple_defaultdoc
class GlobalSolvingStats(NamedTuple):
    """Stores the global statistics for Phase II, which are a sum of the
    statistics of each timeslot."""

    creation_time: float
    """float: sum of the time required to create the LP problem
           for each timeslot."""

    solving_time: float
    """float: sum of the time required to solve the LP problem
           for each timeslot."""

    optimal_cost: float
    """float: sum of the optimal costs as reported by the LP problem
           for each timeslot."""

    status: Status
    """:class:`.Status`: global status computed from the status of
           each timeslot."""

    default_algorithm: Optional[str] = None
    """Currently unused"""


@remove_namedtuple_defaultdoc
class ReservedAllocation(NamedTuple):
    """Stores the number of reserved instances to allocate during the whole reservation
    period."""

    instance_classes: Tuple[InstanceClass, ...]
    """List[:class:`.InstanceClass`, ...]: list of reserved instance classes
           in the allocation."""
    vms_number: Tuple[float, ...]
    """List[float, ...]: list of numbers, representing the number of instance classes
        to be reserved of each type. The corresponding instance class is obtained
        from the ``instance_classes`` attribute using the same index."""


@remove_namedtuple_defaultdoc
class AllocationInfo(NamedTuple):
    """Stores the allocation for a series of timeslots. It can be a single
    timeslot, or the sequence of allocations for the whole reservation period."""

    values: Tuple[Tuple[Tuple[float, ...], ...], ...]
    """Tuple[Tuple[Tuple[float, ...], ...], ...]: contains a list with one element
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

    units: str
    """str: a string identifying the kind of information stored in the ``values``
           field. It can be ``"vms"`` (number of VM instances), ``"cost"`` or any
           currency (cost of these instances) or ``"rph"`` (performance of these
           instances)."""

    apps: Sequence[App]
    """Sequence[:class:`.App`]: is a list of apps to give meaning to the second
           index in ``values``."""

    instance_classes: Sequence[InstanceClass]
    """Sequence[:class:`.InstanceClass`]: is a list of instance classes to give
           meaning to the third index in ``values``."""

    workload_tuples: Sequence[Tuple[float, ...]]
    """Sequence[Tuple[float, ...]]: is a list of workload tuples to give meaning to the
           first index in ``values``. Each element is a tuple with as many values
           as apps, being each one the workload for each app."""

    repeats: List[int] = []
    """List[int]: number of repetitions of each workload_tuple, for the case
    in which the allocation is per load-level (histogram). It can be an empty
    list (default value) for the case in which the allocation is per time-slot."""

    def __repr__(self):
        d0 = len(self.values)
        if self.values:
            d1 = len(self.values[0])
        else:
            d1 = 0
        if d1:
            d2 = len(self.values[0][0])
        else:
            d2 = 0
        return "<{} {}x{}x{}>".format(self.__class__.__name__, d0, d1, d2)


@remove_namedtuple_defaultdoc
class SolutionI(NamedTuple):
    """Stores a solution for phase I."""

    id: str
    "str: arbitrary id for this object."

    problem: Problem
    """:class:`.Problem`: reference to the problem which originated
          this solution."""

    solving_stats: SolvingStats
    """:class:`.SolvingStats`: statistics about this solution."""

    allocation: AllocationInfo
    """:class:`.AllocationInfo`: allocation provided in this solution."""

    reserved_allocation: ReservedAllocation
    """:class:`.ReservedAllocation`: allocation for reserved instances only."""


@remove_namedtuple_defaultdoc
class SolutionII(NamedTuple):
    """Stores a solution for phase II."""

    id: str
    "str: arbitrary id for this object."

    problem: Problem
    """:class:`.Problem`: reference to the problem which originated
          this solution."""

    solving_stats: Sequence[SolvingStats]
    """:Sequence[class:`.SolvingStats`]: list of the SolvingStats for
        each timeslot."""

    global_solving_stats: GlobalSolvingStats
    """:class:`.GlobalSolvingStats`: summary of the solving stats."""

    previous_phase: SolutionI
    """:class:`.SolutionI`: reference to the solution of the previous phase."""

    allocation: AllocationInfo
    """:class:`.AllocationInfo`: allocation for the whole period, built from the
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
            costs_row.append(tuple(costs_app))
        costs.append(tuple(costs_row))

    return alloc._replace(values=tuple(costs), units="cost")


@compute_allocation_cost.register(SolutionI)
@compute_allocation_cost.register(SolutionII)
def _(solution: Union[SolutionI, SolutionII]) -> AllocationInfo:
    return compute_allocation_cost(solution.allocation)


@singledispatch
def compute_allocation_performance(
    alloc: AllocationInfo, performances: PerformanceValues
) -> AllocationInfo:
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
                perfs_app.append(app_alloc[i] * performances[iclass, app])
            perfs_row.append(tuple(perfs_app))
        perfs.append(tuple(perfs_row))
    return alloc._replace(values=tuple(perfs), units="rph")


@compute_allocation_performance.register(SolutionI)
@compute_allocation_performance.register(SolutionII)
def __(
    solution: Union[SolutionI, SolutionII]
) -> AllocationInfo:  # pylint:disable=function-redefined
    return compute_allocation_performance(
        solution.allocation, solution.problem.performances.values
    )


__all__ = [
    "Status",
    "MallooviaStats",
    "SolvingStats",
    "GlobalSolvingStats",
    "AllocationInfo",
    "ReservedAllocation",
    "SolutionI",
    "SolutionII",
    "compute_allocation_cost",
    "compute_allocation_performance",
]
