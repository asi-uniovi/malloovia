"""Module providing high level PhaseI and PhaseII classes which drive the solver"""
from typing import Dict, Tuple, Any, Sequence, Optional
import time
from collections import OrderedDict
import collections.abc
from pulp import PulpSolverError  # type: ignore

from .lpsolver import MallooviaLp, MallooviaLpMaximizeTimeslotPerformance
from .solution_model import (
    SolvingStats,
    GlobalSolvingStats,
    MallooviaStats,
    SolutionI,
    SolutionII,
    AllocationInfo,
    ReservedAllocation,
    Status,
    pulp_to_malloovia_status,
)
from .model import System, Problem, Workload, system_from_problem, check_valid_problem

###############################################################################
# Phase I
###############################################################################
class PhaseI:
    """Interface to the solver for the PhaseI of the method.

    Usage::

        phase_i = PhaseI(problem)
        solution = phase_i.solve()
    """

    def __init__(self, problem: Problem) -> None:
        """Constructor.

        Args:
            problem: the problem (instances, performances and workload per app) to solve.

        Raises:
            ValueError: if the problem stores inconsistent information.
        """
        self.problem = check_valid_problem(problem)
        self.__solution: Optional[SolutionI] = None
        self.__full_solution = None
        self._malloovia_lp: Optional[MallooviaLp] = None
        self.solving_stats = None

    def solve(
        self, gcd: bool = True, solver: Any = None, relaxed: bool = False
    ) -> SolutionI:
        """Creates Malloovia's LP problem, solves it, and returns the solution.

        Args:
            gcd: boolean to denote if quantization using GCD should be used
            solver: optional Pulp solver. It can have custom arguments, such
                as fracGap and maxSeconds.
            relaxed: boolean; if True, the problem uses continuous variables
                instead of integer ones.
        Returns:
            The solution of the problem, which includes solving_stats, reserved_allocation
            and (full) allocation.
        """

        # First creates the problem, then solves it
        creation_time, self._malloovia_lp = _create_problem(
            system=system_from_problem(self.problem),
            workloads=self.problem.workloads,
            relaxed=relaxed,
        )
        solving_time, malloovia_stats = _solve_problem(
            self._malloovia_lp, gcd=gcd, solver=solver
        )

        # Retrieve the solution and store it in a private property
        allocation = None
        reserved_allocation = None
        optimal_cost = None
        if malloovia_stats.status == Status.optimal:
            allocation = self._malloovia_lp.get_allocation()
            reserved_allocation = self._malloovia_lp.get_reserved_allocation()
            optimal_cost = self._malloovia_lp.get_cost()

        solving_stats = SolvingStats(
            algorithm=malloovia_stats,
            creation_time=creation_time,
            solving_time=solving_time,
            optimal_cost=optimal_cost,
        )

        self.__solution = SolutionI(
            id="solution_i_{}".format(self.problem.id),
            problem=self.problem,
            solving_stats=solving_stats,
            reserved_allocation=reserved_allocation,
            allocation=allocation,
        )

        return self.__solution

    @property
    def solution(self):
        """Stored solution of the problem (type :class:`SolutionI`). It is None
        if the problem has not been yet solved."""
        return self.__solution


###############################################################################
# Phase II
###############################################################################
class STWPredictor(collections.abc.Iterable):
    """Abstract base class for short-term workload predictors"""

    # It is abstract because it does not implements __iter__
    # Any attempt to instantiate this class will produce a run-time error
    pass


class OmniscientSTWPredictor(
    STWPredictor
):  # pylint: disable=invalid-name,too-few-public-methods
    """Concrete implementation of STWP_Predictor which knows in advance the STWP for
    all timeslots in the future.

    Implements the iterable interface and when looping over it, it returns one
    tuple at a time, whose elements are :class:`Workload` whose
    ``values`` have a length of 1 (the workload for the next timeslot).
    """

    def __init__(self, stwp: Tuple[Workload, ...]) -> None:
        """Constructor.

        Args:
            stwp: Tuple of :class:`Workload` objects, one per app. Each workload contains
                in the field ``values`` a sequence of predicted workloads for the whole
                reservation period.
        Raises:
            ValueError: if the lengths of the workloads do not match.
        """
        self.stwp = stwp
        self.timeslots = len(stwp[0].values)
        if not all(len(w.values) == self.timeslots for w in stwp):
            raise ValueError("All workloads should have the same length")

    def __iter__(self):
        return (  # Generator expression
            tuple(
                Workload(
                    id=None,
                    description=None,
                    values=(w.values[i],),
                    time_unit=w.time_unit,
                    app=w.app,
                )
                for w in self.stwp
            )
            for i in range(self.timeslots)
        )


class PhaseII:
    """Solves phase II, either for a single timeslot or for the whole reservation period.

    This class is used for solving Phase II. It receives in the constructor (see below)
    a problem  and a solution for Phase I already computed, which contains the
    allocation for the reserved instances.

    It provides the methods :func:`self.solve_timeslot()` to solve a single
    timeslot, and :func:`self.solve_period()` to solve the whole reservation period
    by iteratively solving each timeslot.
    """

    def __init__(
        self,
        problem: Problem,
        phase_i_solution: SolutionI,
        solver: Any = None,
        reuse_rsv: bool = True,
    ) -> None:
        """Constructor.

        Args:
            problem: the problem to solve, usually the same used in Phase I, but it can be
                different as long as it contains references to the same apps and reserved
                instance classes.
            phase_i_solution: the solution returned by Phase I
            solver: optional Pulp solver. It can have custom arguments, such
                as fracGap and maxSeconds.
            reuse_rsv: boolean indicating if reserved instances that were assigned in
                phase I to an application can be reused for another application.
        """
        if phase_i_solution.solving_stats.algorithm.status != Status.optimal:
            raise ValueError("phase_i_solution passed to PhaseII is not optimal")
        self.problem = problem
        self.phase_i_solution = phase_i_solution
        self.solver = solver
        self.reuse_rsv = reuse_rsv

        # Hash table with the already computed solutions for each workload level
        # initially empty
        self._solutions: Dict[
            Tuple[System, Sequence[Workload]], SolutionI
        ] = OrderedDict()

        # Internal handle to the inner malloovia LP solver
        self._malloovia_lp = None

    def solve_timeslot(
        self, workloads: Sequence[Workload], system: System = None, solver: Any = None
    ) -> SolutionI:
        """Solve one timeslot of phase II for the workload received.

        The solution is stored in the field 'self._solutions' using the pairs (system, workloads)
        as keys. If a solution for that key is already present, the same solution is returned.

        Args:
            workloads: tuple with one Workload per app. Only the first value in the
                 ``values`` field of each workload is used, as the prediction for
                 the timeslot to solve.
            system: the part of the problem which does not depend on the workload.
                If ``None``, the system will be extracted from ``self.problem``.
            solver: Pulp solver. It can have custom arguments, such
                as fracGap and maxSeconds.

        Returns:
            The solution for that timeslot, stored in a :class:`SolutionI` object.
        """
        if system is None:
            system = system_from_problem(self.problem)

        if (system, workloads) in self._solutions:
            # This workload was already solved. Nothing to be done
            return self._solutions[system, workloads]

        if not self.reuse_rsv:
            raise NotImplementedError("Solving without reuse is not implemented")

        if solver is None:  # default to class solver
            solver = self.solver

        # Instantiate problem
        creation_time, malloovia_lp = _create_problem(
            system=system,
            workloads=workloads,
            preallocation=self.phase_i_solution.reserved_allocation,
            relaxed=False,
        )
        solving_time, malloovia_stats = _solve_problem(
            malloovia_lp, gcd=False, solver=solver
        )

        # Retrieve the solution and store it in a private property
        allocation = None
        optimal_cost = None
        if malloovia_stats.status == Status.optimal:
            allocation = malloovia_lp.get_allocation()
            optimal_cost = malloovia_lp.get_cost()
        else:
            sol = _solve_dual_problem(
                system=system,
                workloads=workloads,
                preallocation=self.phase_i_solution.reserved_allocation,
                solver=solver,
            )
            creation_time += sol.solving_stats.creation_time
            solving_time += sol.solving_stats.solving_time
            if sol.solving_stats.algorithm.status == Status.optimal:
                malloovia_stats = malloovia_stats._replace(status=Status.overfull)
            else:
                malloovia_stats = malloovia_stats._replace(
                    status=sol.solving_stats.algorithm.status
                )
            optimal_cost = sol.solving_stats.optimal_cost
            allocation = sol.allocation

        solving_stats = SolvingStats(
            algorithm=malloovia_stats,
            creation_time=creation_time,
            solving_time=solving_time,
            optimal_cost=optimal_cost,
        )

        valid_id = "sol_for_{}".format("_".join(str(wl.values[0]) for wl in workloads))
        self._solutions[system, workloads] = SolutionI(
            id=valid_id,
            problem=self.problem,
            solving_stats=solving_stats,
            reserved_allocation=self.phase_i_solution.reserved_allocation,
            allocation=allocation,
        )

        return self._solutions[system, workloads]

    def solve_period(self, predictor: STWPredictor = None) -> SolutionII:
        """Solves the complete reserved period by iteratively solving each timeslot.

        Args:
            predictor: a generator which yields one prediction tuple per timeslot.
                If ``None``, a default :class:`OmniscientSTWPredictor` is instantiated
                which iterates over the Problem.workloads values.

        Returns:
            The global solution for phase II, which contains the allocation for each
            timeslot and SolvingStats for each timeslot.
        """

        system = system_from_problem(self.problem)
        if predictor is None:
            predictor = OmniscientSTWPredictor(self.problem.workloads)
        solutions = []
        for workloads in predictor:
            solutions.append(self.solve_timeslot(system=system, workloads=workloads))
        return self._aggregate_solutions(solutions)

    def _aggregate_solutions(self, solutions):
        """Build a SolutionII object from the data in the _solutions
        attribute. It has to convert the dictionary of Solutions for
        each load level into a single solution which will contain
        a list of stats (per time slot) plus a AllocationInfo with allocations
        per time slot.
        """
        if all(s.solving_stats.algorithm.status == Status.optimal for s in solutions):
            global_status = Status.optimal
        elif any(
            s.solving_stats.algorithm.status == Status.infeasible for s in solutions
        ):
            global_status = Status.infeasible
        elif any(
            s.solving_stats.algorithm.status == Status.overfull for s in solutions
        ):
            global_status = Status.overfull
        else:
            global_status = Status.unknown

        global_solving_stats = GlobalSolvingStats(
            creation_time=sum(s.solving_stats.creation_time for s in solutions),
            solving_time=sum(s.solving_stats.solving_time for s in solutions),
            optimal_cost=sum(s.solving_stats.optimal_cost for s in solutions),
            status=global_status,
        )

        allocation = AllocationInfo(
            apps=solutions[0].allocation.apps,
            instance_classes=solutions[0].allocation.instance_classes,
            workload_tuples=[s.allocation.workload_tuples[0] for s in solutions],
            repeats=[1] * len(solutions),
            values=tuple(s.allocation.values[0] for s in solutions),
            units="vms",
        )

        return SolutionII(
            id="solution_phase_ii_{}".format(self.problem.id),
            problem=self.problem,
            solving_stats=[s.solving_stats for s in solutions],
            previous_phase=self.phase_i_solution,
            global_solving_stats=global_solving_stats,
            allocation=allocation,
        )


class PhaseIIGuided(PhaseII):
    """Extends :class:`PhaseII` class to override the :func:`self.solve_timeslot()` 
    method, to allow it to receive a `preallocation` parameter which enforces some
    minimum number of on-demand instances and a fixed number of reserved instances.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._solutions: Dict[
            Tuple[System, ReservedAllocation, Sequence[Workload]], SolutionI
        ] = OrderedDict()

    def solve_timeslot(
        self,
        workloads: Sequence[Workload],
        system: System = None,
        solver: Any = None,
        preallocation: ReservedAllocation = None,
    ):
        """Solve one timeslot of phase II for the workload received.

        The solution is stored in the field 'self._solutions' using the tuples
        (system, preallocation, workloads) as keys. If a solution for that key
        is already present, the same solution is returned.

        Args:
            workloads: tuple with one Workload per app. Only the first value in the
                 ``values`` field of each workload is used, as the prediction for
                 the timeslot to solve.
            system: the part of the problem which does not depend on the workload.
                If ``None``, the system will be extracted from ``self.problem``.
            solver: Pulp solver. It can have custom arguments, such
                as fracGap and maxSeconds.
            preallocation: allocation for a minimum number of on-demand 
                instances, to keep active from previous timeslots. An external
                driver should compute these numbers and pass them to the 
                solver through this parameter.

        Returns:
            The solution for that timeslot, stored in a :class:`SolutionI` object.
        """
        if system is None:
            system = system_from_problem(self.problem)

        if preallocation is None:
            preallocation = self.phase_i_solution.reserved_allocation
        else:
            res_alloc = self.phase_i_solution.reserved_allocation
            res_ics = res_alloc.instance_classes
            res_vms_number = res_alloc.vms_number
            preallocation = ReservedAllocation(
                instance_classes=res_ics + preallocation.instance_classes,
                vms_number=res_vms_number + preallocation.vms_number,
            )

        if (system, preallocation, workloads) in self._solutions:
            # This workload was already solved. Nothing to be done
            return self._solutions[system, preallocation, workloads]

        if not self.reuse_rsv:
            raise NotImplementedError("Solving without reuse is not implemented")

        if solver is None:  # default to class solver
            solver = self.solver

        # Instantiate problem
        creation_time, malloovia_lp = _create_problem(
            system=system,
            workloads=workloads,
            preallocation=preallocation,
            relaxed=False,
        )
        solving_time, malloovia_stats = _solve_problem(
            malloovia_lp, gcd=False, solver=solver
        )

        # Retrieve the solution and store it in a private property
        allocation = None
        optimal_cost = None
        if malloovia_stats.status == Status.optimal:
            allocation = malloovia_lp.get_allocation()
            optimal_cost = malloovia_lp.get_cost()
        else:
            sol = _solve_dual_problem(
                system=system,
                workloads=workloads,
                preallocation=preallocation,
                solver=solver,
            )
            creation_time += sol.solving_stats.creation_time
            solving_time += sol.solving_stats.solving_time
            if sol.solving_stats.algorithm.status == Status.optimal:
                malloovia_stats = malloovia_stats._replace(status=Status.overfull)
            else:
                malloovia_stats = malloovia_stats._replace(
                    status=sol.solving_stats.algorithm.status
                )
            optimal_cost = sol.solving_stats.optimal_cost
            allocation = sol.allocation

        solving_stats = SolvingStats(
            algorithm=malloovia_stats,
            creation_time=creation_time,
            solving_time=solving_time,
            optimal_cost=optimal_cost,
        )

        valid_id = "sol_for_{}".format("_".join(str(wl.values[0]) for wl in workloads))
        self._solutions[system, preallocation, workloads] = SolutionI(
            id=valid_id,
            problem=self.problem,
            solving_stats=solving_stats,
            reserved_allocation=preallocation,
            allocation=allocation,
        )

        return self._solutions[system, preallocation, workloads]


def _solve_dual_problem(
    system: System,
    workloads: Sequence[Workload],
    preallocation: Optional[ReservedAllocation],
    solver: Any = None,
) -> SolutionI:
    """Uses MallooviaLpMaximizeTimeslotPerformance to solve the dual problem

    Args:
        system: infrastructure, apps and performance of the system
        workloads: list of workloads, one per app
        preallocation: allocation for reserved instances, from phase I, or None

    Returns:
        A :class:`SolutionI` object with the solution which maximizes performance
        in the timeslot.
    """

    malloovia_lp = MallooviaLpMaximizeTimeslotPerformance(
        system=system,
        workloads=workloads,
        preallocation=preallocation,
        relaxed=False,  # TODO: Allow for relaxed in PhaseII?
    )
    start = time.perf_counter()
    malloovia_lp.create_problem()
    creation_time = time.perf_counter() - start

    solving_time, malloovia_stats = _solve_problem(
        malloovia_lp=malloovia_lp, gcd=False, solver=solver
    )

    allocation = malloovia_lp.get_allocation()
    optimal_cost = malloovia_lp.get_cost()

    solving_stats = SolvingStats(
        algorithm=malloovia_stats,
        creation_time=creation_time,
        solving_time=solving_time,
        optimal_cost=optimal_cost,
    )

    return SolutionI(
        id=None,
        problem=None,
        solving_stats=solving_stats,
        reserved_allocation=None,
        allocation=allocation,
    )


# Functions which interface with lpSolver.MallooviaLp to create and solve the problem
def _create_problem(
    system: System,
    workloads: Sequence[Workload],
    preallocation: ReservedAllocation = None,
    relaxed: bool = False,
) -> Tuple[float, MallooviaLp]:
    """Instantiates MallooviaLp class with the problem definition, and calls
    :func:`MallooviaLp.create_problem()`.

    Args:
        system: infrastructure, apps and performance of the system
        workloads: list of workloads, one per app
        preallocation: allocation for reserved instances, from phase I, or None
        relaxed: whether the problem has to be created relaxed or integer.

    Returns:
        The time required to create the problem, and the instance of MallooviaLp
        with the problem already created.
    """
    # Instantiate LP problem
    _malloovia_lp = MallooviaLp(
        system=system, workloads=workloads, preallocation=preallocation, relaxed=relaxed
    )

    # Write the LP problem and measure the time required to create it
    start = time.perf_counter()
    _malloovia_lp.create_problem()
    creation_time = time.perf_counter() - start
    return creation_time, _malloovia_lp


def _solve_problem(
    malloovia_lp: MallooviaLp, gcd: bool, solver: Any
) -> Tuple[float, MallooviaStats]:
    """Calls :func:`MallooviaLp.solve()` and retrieves statistics from the solver.

    Args:
        malloovia_lp: instance of MallooviaLp problem to solve (must be already created)
        gcd: whether the problem has to be solved with GCD method or not.
        solver: the PuLP solver to be used by MallooviaLp.

    Returns:
        The time required to create the problem, and the statistics from the solver."""
    # TODO: decide how to handle gcd

    status = Status.unknown
    lower_bound = None

    # Prepare solver
    if solver is None:
        frac_gap = None
        max_seconds = None
    else:
        frac_gap = solver.fracGap
        max_seconds = solver.maxSeconds

    # Solve the problem and measure the time required
    start = time.perf_counter()
    try:
        malloovia_lp.solve(solver, use_mps=False)
    except PulpSolverError as exception:
        end = time.perf_counter()
        solving_time = end - start
        status = Status.cbc_error
        print(
            "Exception PulpSolverError. Time to failure: {} seconds\n".format(
                solving_time
            ),
            exception,
        )
    else:
        # No exceptions
        end = time.perf_counter()
        solving_time = end - start
        status = pulp_to_malloovia_status(malloovia_lp.pulp_problem.status)

    if status == Status.aborted:
        lower_bound = malloovia_lp.pulp_problem.bestBound

    malloovia_stats = MallooviaStats(
        gcd=gcd,
        frac_gap=frac_gap,
        max_seconds=max_seconds,
        status=status,
        lower_bound=lower_bound,
    )
    return solving_time, malloovia_stats


__all__ = [
    "PhaseI",
    "PhaseII",
    "PhaseIIGuided",
    "STWPredictor",
    "OmniscientSTWPredictor",
]
