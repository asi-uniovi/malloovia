"Tests for time units in malloovia"
import pytest
# import ruamel.yaml
# from jsonschema import validate

# from malloovia import util
from malloovia import phases
from malloovia.solution_model import Status, SolvingStats, SolutionI, MallooviaStats
# from .datapaths import PresetDataPaths

# yaml = ruamel.yaml.YAML(typ='safe')
# yaml.safe_load = yaml.load

from malloovia.model import (LimitingSet, InstanceClass, App, Workload,
                   Problem, System, system_from_problem,
                   PerformanceSet, PerformanceValues, TimeUnit)

from malloovia.solution_model import (
    Status, ReservedAllocation, AllocationInfo, MallooviaHistogram,
    compute_allocation_cost, compute_allocation_performance)

# pylint: disable=invalid-name

class TestTimeUnits:
    def test_time_unit_conversion(self):
        hour = TimeUnit("h")
        assert hour.to("s") == 3600
        assert hour.to("m") == 60

        day = TimeUnit("d")
        assert day.to("h") == 24
        assert day.to("m") == 24*60
        assert day.to("y") == 1/365

        year = TimeUnit("y")
        assert year.to("d") == 365
        assert year.to("h") == 8760

        half_hour = TimeUnit("h", 0.5)
        assert half_hour.to("m") == 30

        week = TimeUnit("d", 7)
        assert week.to("h") == 24*7

    def test_wrong_unit_raises_exception(self):
        with pytest.raises(ValueError, match="Unit 'w' is not valid"):
            wrong_init = TimeUnit("w")

        year = TimeUnit("y")
        with pytest.raises(ValueError, match="Unit 'w' is not valid"):
            wrong_conversion = year.to("w")

class TestMallooviaWithUnits():
    def create_simple_problem(self, time_unit_price="h", time_unit_performance="h", timeslot="h",
                              base_price=100, base_perf=1000, base_workload=2000,
                              n_timeslots=365*24):
        """Creates as simple example problem with one region, two instance classes
        and one app. The workload is constant for the whole period.

        Returns the created problem."""
        max_instances = 20
        region = LimitingSet("Cloud1", name="Cloud1", max_vms=max_instances)
        i0 = InstanceClass(
            "ondemand", name="On Demand", price=base_price, limiting_sets=(region,),
            max_vms=max_instances, is_reserved=False, time_unit=time_unit_price)
        i1 = InstanceClass(
            "reserved", name="Reserved", price=0.8*base_price, limiting_sets=(region,),
            max_vms=max_instances, is_reserved=True, time_unit=time_unit_price)
        app0 = App("App0", name="App0")
        workloads = (
            Workload("ltwp", description="Test", app=app0, values=(base_workload,)*n_timeslots,
                     time_unit=timeslot),
        )
        performances = PerformanceSet(
            id="perfs",
            time_unit=time_unit_performance,
            values=PerformanceValues({
                i0: {app0: base_perf},
                i1: {app0: base_perf}
            })
        )
        return Problem(
            id="example",
            name="PhaseI",
            workloads=workloads,
            instance_classes=(i0,i1),
            performances=performances
        )

    def test_different_units_in_workload(self):
        problem1 = self.create_simple_problem(time_unit_price="h", time_unit_performance="h",
                                              timeslot="h", base_price=100, base_perf=1000,
                                              base_workload=2000, n_timeslots=365*24)
        phaseI1 = phases.PhaseI(problem1)
        solution1 = phaseI1.solve()
        assert solution1.solving_stats.algorithm.status == Status.optimal

        # Now solve the same problem, but with the workload in minutes
        problem2 = self.create_simple_problem(time_unit_price="h", time_unit_performance="h",
                                              timeslot="m", base_price=100, base_perf=1000,
                                              base_workload=2000/60, n_timeslots=365*24*60)
        phaseI2 = phases.PhaseI(problem2)
        solution2 = phaseI2.solve()

        # The solution should be the same, because the performance is the same
        assert solution2.solving_stats.algorithm.status == Status.optimal
        assert solution2.solving_stats.optimal_cost == solution1.solving_stats.optimal_cost
        assert solution1.reserved_allocation == solution2.reserved_allocation

    def test_use_different_unit_in_prices(self):
        problem1 = self.create_simple_problem(time_unit_price="h", time_unit_performance="h",
                                              timeslot="h", base_price=100, base_perf=1000,
                                              base_workload=2000, n_timeslots=365*24)
        phaseI1 = phases.PhaseI(problem1)
        solution1 = phaseI1.solve()
        assert solution1.solving_stats.algorithm.status == Status.optimal

        # Now solve the same problem, but with the prices in minutes, not scaled
        problem2 = self.create_simple_problem(time_unit_price="m", time_unit_performance="h",
                                              timeslot="h", base_price=100, base_perf=1000,
                                              base_workload=2000, n_timeslots=365*24)
        phaseI2 = phases.PhaseI(problem2)
        solution2 = phaseI2.solve()

        # Since 100 is now the price per minute instead of per hour, the total cost should
        # be 60 times the one of the first problem
        assert solution2.solving_stats.algorithm.status == Status.optimal
        assert solution2.solving_stats.optimal_cost == 60 * solution1.solving_stats.optimal_cost
        # But, except for the cost, the solution is equivalent
        assert solution2.allocation.values == solution1.allocation.values

    def test_use_different_unit_in_performances(self):
        problem1 = self.create_simple_problem(time_unit_price="h", time_unit_performance="h",
                                              timeslot="h", base_price=100, base_perf=1000,
                                              base_workload=2000, n_timeslots=365*24)
        phaseI1 = phases.PhaseI(problem1)
        solution1 = phaseI1.solve()
        assert solution1.solving_stats.algorithm.status == Status.optimal

        # Now the same problem, but the performances are expressed in qps instead of rph
        problem2 = self.create_simple_problem(time_unit_price="h", time_unit_performance="s",
                                              timeslot="h", base_price=100, base_perf=1000/3600,
                                              base_workload=2000, n_timeslots=365*24)
        phaseI2 = phases.PhaseI(problem2)
        solution2 = phaseI2.solve()

        # The solution should be the same, because the performance is the same (only scaled)
        assert solution2.solving_stats.algorithm.status == Status.optimal
        assert solution2.solving_stats.optimal_cost == solution1.solving_stats.optimal_cost
        assert solution2.allocation.values == solution1.allocation.values

    def test_use_different_unit_in_phaseII_workload(self):
        # In phase I, the prices and performances are expressed per hour
        # The workload is also per hour. To reduce the size of the problem,
        # we use 24h as reservation period instead of 8760
        phase_i_problem = self.create_simple_problem(
            time_unit_price="h", time_unit_performance="h",
            timeslot="h", base_price=100, base_perf=1000,
            base_workload=2000, n_timeslots=24)
        phaseI = phases.PhaseI(phase_i_problem)
        solution_i = phaseI.solve()
        assert solution_i.solving_stats.algorithm.status == Status.optimal

        # For phase II, we keep the same instance classes (prices and performances)
        # but use a STWP expressed in minutes
        app0 = phase_i_problem.workloads[0].app
        phase_ii_problem = phase_i_problem._replace(
            workloads = (
                Workload("wl_app0", description="Test", app=app0, values=(2000/3600,)*24*60,
                         time_unit="m"),
            )
        )
        phase_ii = phases.PhaseII(
            problem=phase_ii_problem,
            phase_i_solution=solution_i
        )
        solution_ii = phase_ii.solve_period()

        # Since the workload was scaled, it is essentially the same, so the phase II solution
        # should be equal to phase I solution, except for rounding errors
        assert (abs(solution_ii.global_solving_stats.optimal_cost
                - solution_i.solving_stats.optimal_cost) <= 0.0001)

