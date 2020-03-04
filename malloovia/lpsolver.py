# coding: utf-8
#  import pandas as pd
"""Malloovia interface to LP solver"""

from typing import Sequence, List, Any
from itertools import product as cartesian_product
from inspect import ismethod
from collections import namedtuple
from uuid import uuid4
import os

import pulp  # type: ignore

from pulp import (
    LpContinuous,
    LpInteger,
    LpVariable,
    lpSum,
    LpProblem,
    LpMinimize,
    LpMaximize,
    PulpSolverError,
    COIN_CMD,
    log,
    subprocess,
)

from .solution_model import (
    MallooviaHistogram,
    ReservedAllocation,
    AllocationInfo,
    Status,
    pulp_to_malloovia_status,
)
from .model import System, Workload, App, TimeUnit

LpProblem.bestBound = None  # Add new attribute to pulp problems


class MallooviaLp:
    """Solves the allocation problem, using Linear Programming.

    This class contains methods to create a linear programming problem
    (using PuLP), to add restrictions and extra variables to it,
    to solve it (using PuLP supported solvers), and to retrieve
    the solution in a format amenable to further analysis and display.

    The LP problem instantiates these variables:

    - For reserved instances: ``Y_(_a,_ic)``, where ``Y`` is a fixed prefix,
      ``a`` is a string representation of each application and ``ic`` is the string
      representation of each reserved instance class considered.
      After solving the LP problem, the value of the variable is the number of
      reserved machines of instance class `ic` for application `a`, for the whole
      reservation period.

    - For on-demand instances: ``X_(_a,_ic,_l)``, where ``X`` is a fixed prefix,
      ``a`` is a string representation of each application, ``ic`` is the string
      representation of each on-demand instance class considered and ``l`` is a
      string representation of a "workload tuple", which is a tuple of numbers,
      e.g: ``(1230, 442, 123)``, each one representing the workload of one of the apps.
      After solving the LP problem, the value of the variable is the number of
      on-demand machines of instance class `ic` deployed for application `a` at a
      timeslot which has a workload prediction equal to the tuple ``l``.

    Intended usage:

    1. Instantiate the class (see constructor parameters below).
    2. Call object's ``.create_problem()``.
    3. Call object's ``.solve()``.
    4. Retrieve solution by calling object's ``.get_allocation()`` to get the solution
       for all variables, or ``.get_reserved_allocation()`` to get ony the number of
       reserved instances of each type.
    5. Retrieve the cost of the solution via object's ``.get_solution()``.

    You can use object's property ``pulp_problem`` to access the PuLP problem object
    which represents the linear programming problem, to inspect or save it if required.
    """

    def __init__(
        self,
        system: System,
        workloads: Sequence[Workload],
        preallocation: ReservedAllocation = None,
        relaxed: bool = False,
    ) -> None:
        """Constructor:

        Args:
            system: namedtuple containing "name", "apps", "instance_classes"
                and "performances" for the problem to solve.
            workloads: list of workloads, one per app. Each workload
                is a namedtuple which contains a reference to the app, and a sequence
                of N numbers which is the prediction for the next N timeslots. This
                sequence must have the same length for all workloads in the list.
            preallocation: number of reserved instances which are
                preallocated. In phase I this parameter can be omitted (defaults to ``None``),
                and in phase II it should contain the object returned by
                ``get_reserved_allocation()`` after solving phase I.
            relaxed: if ``True``, the problem uses continuous variables
                instead of integer ones.
        """
        self.system = system
        # Ensure that the workloads received are ordered by the field app in the same
        # ordering than the list system.apps
        self.workloads = reorder_workloads(workloads, system.apps)
        if preallocation is None:
            self.fixed_vms = None
        else:
            assert len(preallocation.instance_classes) == len(
                preallocation.vms_number
            ), (
                "preallocation is wrong, the number of elements in instance_classes and in "
                "vms_number must be the same"
            )
            self.fixed_vms = dict(
                zip(preallocation.instance_classes, preallocation.vms_number)
            )
        self.relaxed = relaxed
        self.pulp_problem: Any = None
        self.load_hist = get_load_hist_from_load(self.workloads)
        self.solver_called = False

        # CookedData  stores some info required when building the problem, so that
        # this data is gathered only once, during __init__, and used when required
        CookedData = namedtuple(  # pylint: disable=invalid-name
            "CookedData",
            [
                "map_dem",
                "map_res",
                "instances_res",
                "instances_dem",
                "limiting_sets",
                "instance_prices",
                "instance_perfs",
            ],
        )

        # Separate the instances in two types: reserved and on-demand
        # Also create dictionaries for fast lookup of price and performance, converted
        # to the timeslot units
        instances_res = []
        instances_dem = []
        instance_prices = {}
        instance_perfs = {}
        timeslot_length = self.workloads[0].time_unit
        for iclass in system.instance_classes:
            instance_prices[iclass] = iclass.price / TimeUnit(iclass.time_unit).to(
                timeslot_length
            )
            for app in self.system.apps:
                instance_perfs[iclass, app] = self.system.performances.values[
                    iclass, app
                ] / TimeUnit(self.system.performances.time_unit).to(timeslot_length)
            if iclass.is_reserved:
                instances_res.append(iclass)
            else:
                instances_dem.append(iclass)

        # Compute the set of LimitingSets (clouds), extracted
        # from the instances
        limiting_sets = set()
        for iclass in system.instance_classes:
            limiting_sets.update(iclass.limiting_sets)

        # Store cooked data
        self.cooked = CookedData(
            map_dem=None,  # To be updated later by create_variables
            map_res=None,
            instances_res=instances_res,
            instances_dem=instances_dem,
            instance_prices=instance_prices,
            instance_perfs=instance_perfs,
            limiting_sets=limiting_sets,
        )

    def _create_variables(self) -> None:
        """Creates the set of variables Y* and X* of the PuLP problem.

        Override it if you need to create extra variables (first use
        ``super().create_variables()`` to call the base class method)."""
        if self.relaxed:
            kind = LpContinuous
        else:
            kind = LpInteger

        # List all combinations of apps and instances and workloads
        comb_res = cartesian_product(self.system.apps, self.cooked.instances_res)
        comb_dem = cartesian_product(
            self.system.apps, self.cooked.instances_dem, self.load_hist.keys()
        )
        map_res = LpVariable.dicts("Y", comb_res, 0, None, kind)
        map_dem = LpVariable.dicts("X", comb_dem, 0, None, kind)
        self.cooked = self.cooked._replace(map_res=map_res, map_dem=map_dem)

    def _cost_function(self) -> None:
        """Adds to the LP problem the function to optimize.

        The function to optimize is the cost of the deployment. It is computed as
        the sum of all Y_a_ic multiplied by the length of the period and by the price/timeslot
        of each reserved instance class plus all X_a_ic_l multiplied by the price/timeslot
        of each on-demand instance class and by the number of times that workload ``l``
        appears in the period."""

        period_length = sum(self.load_hist.values())

        self.pulp_problem += (
            lpSum(
                [
                    self.cooked.map_res[_a, _ic]
                    * self.cooked.instance_prices[_ic]
                    * period_length
                    for _a in self.system.apps
                    for _ic in self.cooked.instances_res
                ]
                + [
                    self.cooked.map_dem[_a, _ic, _l]
                    * self.cooked.instance_prices[_ic]
                    * self.load_hist[_l]
                    for _a in self.system.apps
                    for _ic in self.cooked.instances_dem
                    for _l in self.load_hist.keys()
                ]
            ),
            "Objective: minimize cost",
        )

    def create_problem(self) -> "MallooviaLp":
        """Creates the PuLP problem with all variables and restrictions.

        Returns:
          pulp.LpProblem: instance of the PuLP problem.
        """

        # Create the linear programming problem
        self.pulp_problem = LpProblem(self.system.name, LpMinimize)

        # Once we have the variables represented as tuples, we use
        # the tuples to create the linear programming variables for pulp
        self._create_variables()

        # Create the goal function
        self._cost_function()

        # Add all restrictions indicated with functions *_restriction
        # in this class
        self._add_all_restrictions()

        return self

    def _add_all_restrictions(self) -> None:
        """This functions uses introspection to discover all implemented
        methods whose name ends with ``_restriction``, and runs them all."""
        for name in dir(self):
            attribute = getattr(self, name)
            if ismethod(attribute) and name.endswith("_restriction"):
                attribute()

    def performance_restriction(self) -> None:
        """Adds performance restriction to the problem.

        This restriction forces, for each workload tuple, the performance of the
        solution to be greater than or equal to that workload level for
        all applications.
        """
        for i, app in enumerate(self.system.apps):
            perf_reserved = []
            for ins in self.cooked.instances_res:
                perf_reserved.append(
                    self.cooked.map_res[app, ins] * self.cooked.instance_perfs[ins, app]
                )
            for load in self.load_hist.keys():
                perf_ondemand = []
                for ins in self.cooked.instances_dem:
                    perf_ondemand.append(
                        self.cooked.map_dem[app, ins, load]
                        * self.cooked.instance_perfs[ins, app]
                    )
                self.pulp_problem += (
                    lpSum(perf_reserved + perf_ondemand) >= load[i],
                    "Minimum performance for application {} "
                    "when workload is {}".format(app, load),
                )
        return

    def limit_instances_per_class_restriction(
        self
    ) -> None:  # pylint: disable=invalid-name
        """Adds ``max_vms`` per instance class restriction.

        If the ``ic`` instance has a ``max_vms`` attribute, this is a limit for all
        ``Y_*_ic`` and ``X_*_ic_*`` variables."""
        for ins in self.system.instance_classes:
            if ins.max_vms == 0:
                continue  # No limit for this instance class

            if ins.is_reserved:
                self.pulp_problem += (
                    lpSum(self.cooked.map_res[app, ins] for app in self.system.apps)
                    <= ins.max_vms,
                    "Max instances reserved " "instance class {}".format(ins),
                )
            else:
                for load in self.load_hist.keys():
                    self.pulp_problem += (
                        lpSum(
                            self.cooked.map_dem[app, ins, load]
                            for app in self.system.apps
                        )
                        <= ins.max_vms,
                        "Max instances for on-demand instance "
                        "class {} when workload is {}".format(ins, load),
                    )

    def set_fixed_instances_restriction(self) -> None:
        """Adds restrictions for variables with pre-fixed values.

        For every ``ic`` in ``self.fixed_vms`` a restriction is
        added which forces the total number of those instance classes in
        the solution to be at equal to a given value for reserved instances,
        and at least equal to a given value for on-demand instances.
        This is used mainly in phase II to ensure that reserved instances
        are fixed, or to allow to keep at least some number of on-demand
        instances running from previous timeslots, when using "guided"
        strategies"."""

        if self.fixed_vms is None:  # No fixed instances, we are in PhaseI
            return
        for ins, value in self.fixed_vms.items():
            if ins.is_reserved:
                self.pulp_problem += (
                    lpSum(self.cooked.map_res[app, ins] for app in self.system.apps)
                    == value,
                    "Reserved instance class {} " "is fixed to {}".format(ins, value),
                )
            else:
                for load in self.load_hist.keys():
                    self.pulp_problem += (
                        lpSum(
                            self.cooked.map_dem[app, ins, load]
                            for app in self.system.apps
                        )
                        >= value,
                        "On-demand instance class {} is at least {} "
                        "when workload is {}".format(ins, value, load),
                    )

    def limit_instances_per_limiting_set_restriction(
        self
    ) -> None:  # pylint: disable=invalid-name
        """Adds ``max_vms`` per limiting set restriction.

        If the limiting set provides a max_vms > 0, then the sum of all
        instances which are member of that limiting set should be limited
        to that maximum."""
        for cloud in self.cooked.limiting_sets:
            if cloud.max_vms == 0:
                continue  # No restriction for this limiting set

            for load in self.load_hist.keys():
                self.pulp_problem += (
                    lpSum(
                        [
                            self.cooked.map_res[app, ic]
                            for app in self.system.apps
                            for ic in self.cooked.instances_res
                            if cloud in ic.limiting_sets
                        ]
                        + [
                            self.cooked.map_dem[app, ic, load]
                            for app in self.system.apps
                            for ic in self.cooked.instances_dem
                            if cloud in ic.limiting_sets
                        ]
                    )
                    <= cloud.max_vms,
                    "Max instances for limiting set {} "
                    "when workload is {}".format(cloud, load),
                )

    def limit_cores_per_limiting_set_restriction(
        self
    ) -> None:  # pylint: disable=invalid-name
        """Adds ``max_cores`` per limiting set restriction.

        If the limiting set provides a max_cores > 0, then the sum of all
        instance cores among all instance classes which are member of that
        limiting set should be limited to that maximum."""
        for cloud in self.cooked.limiting_sets:
            if cloud.max_cores == 0:
                continue  # No restriction for this limiting set

            for load in self.load_hist.keys():
                self.pulp_problem += (
                    lpSum(
                        [
                            self.cooked.map_res[app, ic] * ic.cores
                            for app in self.system.apps
                            for ic in self.cooked.instances_res
                            if cloud in ic.limiting_sets
                        ]
                        + [
                            self.cooked.map_dem[app, ic, load] * ic.cores
                            for app in self.system.apps
                            for ic in self.cooked.instances_dem
                            if cloud in ic.limiting_sets
                        ]
                    )
                    <= cloud.max_cores,
                    "Max cores for limiting set {} "
                    "when workload is {}".format(cloud, load),
                )

    def solve(self, *args, **kwargs):
        """Calls PuLP solver.

        Args:
            *args: positional args passed to ``LpProblem.solve()``
            \\**kwargs: keyword args passed to ``LpProblem.solve()``.

        Returns:
            the value returned by ``LpProblem.solve()``.
        """
        self.solver_called = True
        return self.pulp_problem.solve(*args, **kwargs)

    def get_status(self) -> Status:
        """Returns the status of the problem"""
        if not self.solver_called:
            return Status.unsolved
        return pulp_to_malloovia_status(self.pulp_problem.status)

    def get_cost(self) -> float:
        """Gets the cost of the problem, obtained after solving it.

        Returns:
            The cost of the optimal solution found by PuLP.

        Raises:
            ValueError: when the problem is yet unsolved.
        """
        if self.pulp_problem.status != pulp.LpStatusOptimal:
            raise ValueError("Cannot get the cost when the status is not optimal")

        return pulp.value(self.pulp_problem.objective)

    def get_allocation(self) -> AllocationInfo:
        """Retrieves the allocation given by the solution of the LP problem.

        Returns:
            The allocation given by the solution.

        Raises:
            ValueError: if no solution is available (unsolved or infeasible problem)
        """

        if self.pulp_problem.status != pulp.LpStatusOptimal:
            raise ValueError("Cannot get the cost when the status is not optimal")

        workload_tuples = []
        repeats = []
        allocation = []
        for load, repeat in self.load_hist.items():
            workload_tuples.append(load)
            repeats.append(repeat)
            workload_allocation = []
            for app in self.system.apps:
                row = list(
                    self.cooked.map_res[app, i].varValue
                    for i in self.cooked.instances_res
                )
                row.extend(
                    self.cooked.map_dem[app, i, load].varValue
                    for i in self.cooked.instances_dem
                )
                workload_allocation.append(tuple(row))
            allocation.append(tuple(workload_allocation))
        return AllocationInfo(
            apps=tuple(self.system.apps),
            instance_classes=tuple(
                self.cooked.instances_res + self.cooked.instances_dem
            ),
            workload_tuples=workload_tuples,
            repeats=repeats,
            values=tuple(allocation),
            units="vms",
        )

    def get_reserved_allocation(self) -> ReservedAllocation:
        """Retrieves the allocation of reserved instances from the solution of the LP problem.

        Returns:
            The total number of reserved instance classes of each
            type to be purchased for the whole reservation period.
        Raises:
            ValueError: if no solution is available (unsolved or infeasible problem)
        """
        # Returns the solution as a list of numbers, each one
        # representing the required number of vms of each reserved type, stored
        # in the field "vms_number" of the object.

        # This number is valid for any workload tuple, and for every timeslot
        # in the reservation period. Also, it does not depend on the applications
        # because it is the total number of reserved instances for all apps.

        # The returned class also stores the list "instance_classes" which provides
        # the instance class associated with each index in the above table.

        # So, if r is the value returned, the value of r.vms_number[i]
        # (being i an integer) is the number of VMs to be allocated
        # from reserved instance class r.instance_classes[i], for every
        # timeslot and for the set of all apps.

        # This is all the information required for PhaseII.

        if self.pulp_problem.status != pulp.LpStatusOptimal:
            raise ValueError("Cannot get the cost when the status is not optimal")

        allocation: List[float] = []
        for _ in self.load_hist:  # Loop over all possible workloads
            workload_allocation: List[float] = []
            for iclass in self.cooked.instances_res:
                i_allocation = sum(
                    self.cooked.map_res[app, iclass].varValue
                    for app in self.system.apps
                )
                workload_allocation.append(i_allocation)

            # The obtained allocation MUST be the same for any workload
            assert allocation == [] or allocation == workload_allocation
            allocation = workload_allocation

        return ReservedAllocation(
            instance_classes=tuple(self.cooked.instances_res),
            vms_number=tuple(allocation),
        )


class ShortReprTuple(tuple):
    """This class implements a tuple whose repr is not standard
    but uses instead the hash of the tuple, to ensure a constant
    length of the repr.
    
    This is required to store keys in the histogram, because they
    are used to name LP variables which otherwise would have
    a name too long for the solver if the number of apps is large.
    """
    def __repr__(self):
        return str(hash(self))

def get_load_hist_from_load(workloads: Sequence[Workload]) -> MallooviaHistogram:
    """Computes the histogram of the workloads.

    Args:
        workloads: a sequence of :class:`Workload` objects, each one
            containing the fields ``app`` (which identifies the app producing this
            workload) and ``values`` (which stores a sequence of numbers representing
            the workload for each timeslot for that app).
    Returns:
        A dictionary where the key is the workload for one timeslot,
        expressed as a tuple with one element for each application, and the value
        is the number of timeslots in which that workload was found.
    """

    hist = MallooviaHistogram()
    hist.apps = tuple(w.app for w in workloads)
    timeslots = len(workloads[0].values)
    # Ensure that all workloads have the same length and units
    assert all(
        len(w.values) == timeslots for w in workloads
    ), "All workloads should have the same length"
    # Iterate over tuples of loads, one tuple per timeslot
    workload_tuples = zip(*(w.values for w in workloads))
    for load in workload_tuples:
        hist[ShortReprTuple(load)] += 1
    return hist


def reorder_workloads(
    workloads: Sequence[Workload], apps: Sequence[App]
) -> Sequence[Workload]:
    """Returns the a new workload list ordered as the list of apps.

    Args:
        workloads: Sequence of workloads to reorder
        apps: Sequence of apps which dictate the new ordering

    Returns:
        A new sequence of workloads, ordered by app in the order given by apps argument.
    """
    map_apps_workloads = {workload.app: workload for workload in workloads}
    ordered_workloads = []
    for app in apps:
        ordered_workloads.append(map_apps_workloads[app])
    return tuple(ordered_workloads)


class MallooviaLpMaximizeTimeslotPerformance(MallooviaLp):
    """Find the allocation which maximizes performance for a single timeslot.

    This problem is the dual of MallooviaLp. Instead of minimizing the cost
    while providing the minimum performances, the problem to solve now is
    to maximize the performance without breaking the limits.

    The class inherits from Malloovia the initialization methods as well as
    the ones to get the cost and allocation of the solution, but overrides
    the function to be optimized and some of the constraints.
    """

    def _cost_function(self) -> None:
        """Adds to the LP problem the function to optimize (maximize in this case).

        The function to optimize is the performance of the deployment. However, since
        the system is composed to several applications, no single "performance" exists.
        The solution is to maximize the "fraction of performance fulfilled", i.e., the
        sum of `X(_a,_ic,_l)*_ic.performance/_l[a]` among all `_a` and `_ic`.
        """
        workloads = {wl.app: wl.values[0] for wl in self.workloads}

        self.pulp_problem += (
            lpSum(
                [
                    self.cooked.map_res[_a, _ic]
                    * self.cooked.instance_perfs[_ic, _a]
                    / workloads[_a]
                    for _a in self.system.apps
                    for _ic in self.cooked.instances_res
                ]
                + [
                    self.cooked.map_dem[_a, _ic, _l]
                    * self.cooked.instance_perfs[_ic, _a]
                    / workloads[_a]
                    for _a in self.system.apps
                    for _ic in self.cooked.instances_dem
                    for _l in self.load_hist.keys()
                ]
            ),
            "Objective: maximize fulfilled workload fraction",
        )

    def create_problem(self) -> "MallooviaLpMaximizeTimeslotPerformance":
        """This method creates the PuLP problem, and calls other
        methods to add variables and restrictions to it.
        It initializes the attribute 'self.prob' with the
        instance of the PuLP problem created.
        """

        # Create the linear programming problem
        self.pulp_problem = LpProblem(self.system.name, LpMaximize)

        # Create the linear programming variables for pulp
        self._create_variables()

        # Create the goal function
        self._cost_function()

        # Add all restrictions indicated with functions *_restriction
        # in this class
        self._add_all_restrictions()

        return self

    def performance_restriction(self) -> None:
        """Adds performance restriction to the problem.

        This restriction forces, for each workload tuple, the performance of the
        solution to be less than or equal to that workload level, for
        all applications.
        """
        for i, app in enumerate(self.system.apps):
            perf_reserved = []
            for ins in self.cooked.instances_res:
                perf_reserved.append(
                    self.cooked.map_res[app, ins] * self.cooked.instance_perfs[ins, app]
                )
            for load in self.load_hist.keys():
                perf_ondemand = []
                for ins in self.cooked.instances_dem:
                    perf_ondemand.append(
                        self.cooked.map_dem[app, ins, load]
                        * self.cooked.instance_perfs[ins, app]
                    )
                self.pulp_problem += (
                    lpSum(perf_reserved + perf_ondemand) <= load[i],
                    "Maximum performance for application {} "
                    "when workload is {}".format(app, load),
                )

    def get_cost(self) -> float:
        """Gets the cost of the problem, obtained after solving it.

        Returns:
            The cost of the optimal solution found by PuLP.

        Raises:
            ValueError: when the problem is yet unsolved.
        """
        if self.pulp_problem.status == pulp.LpStatusNotSolved:  # Not solved
            raise ValueError("Cannot get the cost of an unsolved problem")
        return sum(
            self.cooked.instance_prices[ic] * self.cooked.map_res[app, ic].varValue
            for ic in self.cooked.instances_res
            for app in self.system.apps
        ) + sum(
            self.cooked.instance_prices[ic]
            * self.cooked.map_dem[app, ic, wl].varValue
            * self.load_hist[wl]
            for ic in self.cooked.instances_dem
            for app in self.system.apps
            for wl in self.load_hist.keys()
        )


# The following function is used to monkey patch part of PuLP code.
# This modification is aimed to get the value of the optimal best bound
# which is provided by CBC solver as part of the solution, even if
# the solution could not be found due to a time limit
#
# PuLP does not recover this value, but for our analysis is useful
# to estimate the worst-case error of our approximation when the
# exact solution cannot be found in a reasonable time.
#
# The code patches the part in which PuLP calls CBC, so that the standard
# output of CBC is redirected to a logfile. When CBC exits, the code
# inspects the logfile and locates the bestBound value, storing it
# as part of the problem to make it accessible to the python code.
#
# This patch only works when the solver is COIN.


# pylint: disable=invalid-name,too-many-locals,missing-docstring,bare-except,too-many-branches,too-many-statements
def _solve_CBC_patched(self, lp, use_mps=True): # pragma: no cover
    """Solve a MIP problem using CBC, patched from original PuLP function
    to save a log with cbc's output and take from it the best bound."""

    def takeBestBoundFromLog(filename):
        try:
            with open(filename, "r") as f:
                for l in f:
                    if l.startswith("Lower bound:"):
                        return float(l.split(":")[-1])
        except:
            pass
        return None

    if not self.executable(self.path):
        raise PulpSolverError("Pulp: cannot execute %s cwd: %s" %
                              (self.path, os.getcwd()))
    if not self.keepFiles:
        uuid = uuid4().hex
        tmpLp = os.path.join(self.tmpDir, "%s-pulp.lp" % uuid)
        tmpMps = os.path.join(self.tmpDir, "%s-pulp.mps" % uuid)
        tmpSol = os.path.join(self.tmpDir, "%s-pulp.sol" % uuid)
        tmpSol_init = os.path.join(self.tmpDir, "%s-pulp_init.sol" % uuid)
    else:
        tmpLp = lp.name+"-pulp.lp"
        tmpMps = lp.name+"-pulp.mps"
        tmpSol = lp.name+"-pulp.sol"
        tmpSol_init = lp.name + "-pulp_init.sol"
    if use_mps:
        vs, variablesNames, constraintsNames, objectiveName = lp.writeMPS(tmpMps, rename = 1)
        cmds = ' '+tmpMps+" "
        if lp.sense == LpMaximize:
            cmds += 'max '
    else:
        vs = lp.writeLP(tmpLp)
        # In the Lp we do not create new variable or constraint names:
        variablesNames = dict((v.name, v.name) for v in vs)
        constraintsNames = dict((c, c) for c in lp.constraints)
        objectiveName = None
        cmds = ' '+tmpLp+" "
    if self.mip_start:
        self.writesol(tmpSol_init, lp, vs, variablesNames, constraintsNames)
        cmds += 'mips {} '.format(tmpSol_init)
    if self.threads:
        cmds += "threads %s "%self.threads
    if self.fracGap is not None:
        cmds += "ratio %s "%self.fracGap
    if self.maxSeconds is not None:
        cmds += "sec %s "%self.maxSeconds
    if self.presolve:
        cmds += "presolve on "
    if self.strong:
        cmds += "strong %d " % self.strong
    if self.cuts:
        cmds += "gomory on "
        # cbc.write("oddhole on "
        cmds += "knapsack on "
        cmds += "probing on "
    for option in self.options:
        cmds += option+" "
    if self.mip:
        cmds += "branch "
    else:
        cmds += "initialSolve "
    cmds += "printingOptions all "
    cmds += "solution "+tmpSol+" "
    # if self.msg:
    #     pipe = None
    # else:
    #     pipe = open(os.devnull, 'w')
    log.debug(self.path + cmds)
    with open(tmpLp + ".log", 'w') as pipe:
        cbc = subprocess.Popen((self.path + cmds).split(), stdout=pipe,
                               stderr=pipe)
        if cbc.wait() != 0:
            raise PulpSolverError("Pulp: Error while trying to execute " +
                                  self.path)
    if not os.path.exists(tmpSol):
        raise PulpSolverError("Pulp: Error while executing "+self.path)
    if use_mps:
        status, values, reducedCosts, shadowPrices, slacks, sol_status = \
            self.readsol_MPS(tmpSol, lp, lp.variables(), variablesNames, constraintsNames)
    else:
        status, values, reducedCosts, shadowPrices, slacks, sol_status = self.readsol_LP(
            tmpSol, lp, lp.variables()
        )
    lp.assignVarsVals(values)
    lp.assignVarsDj(reducedCosts)
    lp.assignConsPi(shadowPrices)
    lp.assignConsSlack(slacks, activity=True)
    lp.assignStatus(status, sol_status)
    lp.bestBound = takeBestBoundFromLog(tmpLp + ".log")
    if not self.keepFiles:
        for f in [tmpMps, tmpLp, tmpSol, tmpSol_init]:
            try:
                os.remove(f)
            except:
                pass
    return status


# Monkey patching
COIN_CMD.solve_CBC = _solve_CBC_patched


__all__ = [
    "MallooviaLp",
    "get_load_hist_from_load",
    "MallooviaLpMaximizeTimeslotPerformance",
]
