"""Testing the new interface to malloovia"""
import pytest
import random
import copy
import os
from unittest.mock import patch
from pulp import (COIN, PulpSolverError)

from malloovia.model import (LimitingSet, InstanceClass, App, Workload,
                   Problem, System, system_from_problem,
                   PerformanceSet, PerformanceValues)
from malloovia import util
from malloovia import phases
from malloovia.solution_model import (
    Status, ReservedAllocation, AllocationInfo, MallooviaHistogram,
    compute_allocation_cost, compute_allocation_performance)
from malloovia import lpsolver
from .datapaths import PresetDataPaths

# pylint: disable=invalid-name
# Test functions have unwieldy names

class PresetProblemPaths(PresetDataPaths):
    """This class stores in self.problems a dictionary with the paths to the
    yaml files which store the problem examples"""
    def setup(self):
        super().setup()
        self.problems = {}
        for problem in ("problem1", "problem2", "problem3"):
            self.problems[problem] = self.get_problem("%s.yaml" % problem)

class TestProblemCreation:
    """Tests the creation of valid and invalid problems, from code"""
    def test_detect_wrong_workload(self):
        "Detect mismatch in workload lengths"
        limiting_set = LimitingSet("Cloud", name="Cloud", max_vms=20)
        instance = InstanceClass(
            "Instance", name="Instance", limiting_sets=(limiting_set,), max_vms=10,
             price=10, time_unit="h")
        app0 = App("App0", name="App0")
        app1 = App("App1", name="App1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32), time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                instance: {app0: 10, app1: 500},
                })
            )
        problem = Problem(
            id="example",
            name="Test problem",
            workloads=workloads,
            instance_classes=(instance,),
            performances=performances
        )
        with pytest.raises(ValueError, match="should have the same length"):
            problem = phases.PhaseI(problem)

    def test_wrong_performances_missing_ic(self):
        "Detect when the performance for one instance_class is missing"
        limiting_set = LimitingSet("Cloud", name="Cloud", max_vms=20)
        instance1 = InstanceClass(
            "Instance1", name="Instance", limiting_sets=(limiting_set,), max_vms=10,
             price=10, time_unit="h")
        instance2 = InstanceClass(
            "Instance2", name="Instance", limiting_sets=(limiting_set,), max_vms=10,
             price=10, time_unit="h")
        app0 = App("App0", name="App0")
        app1 = App("App1", name="App1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32, 40), time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                instance1: {app0: 10, app1: 500},
                # Wrong, instance2 performance is missing
                })
            )
        problem = Problem(
            id="example",
            name="Test problem",
            workloads=workloads,
            instance_classes=(instance1, instance2),
            performances=performances
        )
        expected_msg = "Performance data for {} is missing".format(instance2)
        with pytest.raises(ValueError) as excp:
            problem = phases.PhaseI(problem)
        assert expected_msg == str(excp.value)

    def test_wrong_performances_missing_app(self):
        "Detect when the performance for one app is missing"
        limiting_set = LimitingSet("Cloud", name="Cloud", max_vms=20)
        instance1 = InstanceClass(
            "Instance1", name="Instance1", limiting_sets=(limiting_set,), price=10, max_vms=10,
            time_unit="h")
        instance2 = InstanceClass(
            "Instance2", name="Instance2", limiting_sets=(limiting_set,), price=10, max_vms=10,
            time_unit="h")
        app0 = App("App0", name="App0")
        app1 = App("App1", name="App1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32, 34), time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                instance1: {app0: 10, app1: 500},
                instance2: {app0: 10} # Error, missing app1
                })
            )
        problem = Problem(
            id="example",
            name="Test problem",
            workloads=workloads,
            instance_classes=(instance1, instance2),
            performances=performances
        )
        expected_msg = "Performance data for {} in {} is missing".format(app1, instance2)
        with pytest.raises(ValueError) as excp:
            problem = phases.PhaseI(problem)
        assert expected_msg == str(excp.value)

    def test_create_problem1_using_api(self):
        """Simple test (1region, 2inst, 2aps, 4timeslots), solvable"""
        # Only one region and two instances: one on-demand, other, reserved.
        # There are two apps and four time slots

        # No restriction for on_demand (max_vms=0), to have better testing coverage
        amazon_dem = LimitingSet("Cloud1", name="Cloud1", max_vms=0)
        amazon_res = LimitingSet("CloudR", name="CloudR", max_vms=20)

        m3large = InstanceClass(
            "m3large", name="m3large", limiting_sets=(amazon_dem,), max_vms=20, price=10,
            time_unit="h")
        m3large_r = InstanceClass(
            "m3large_r", name="m3large_r", limiting_sets=(amazon_res,), max_vms=20, price=7,
            time_unit="h", is_reserved=True)
        app0 = App("app0", name="Test app0")
        app1 = App("app1", name="Test app1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32, 30, 30),
                     time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194, 1003),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                m3large: {app0: 10, app1: 500},
                m3large_r: {app0: 10, app1: 500}
                })
            )
        problem_phase_i = Problem(
            id="example",
            name="Test problem",
            workloads=workloads,
            instance_classes=(m3large, m3large_r),
            performances=performances)

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32
        # to_yaml = util.problems_to_yaml({"p1": problem_phase_i})
        # with (open("test_data/problems/problem1.yaml", "w")) as output:
        #     output.write(to_yaml)

    def test_create_problem2_using_api(self):
        """Simple test (1region, 2inst, 2aps, 4timeslots),
        infeasible due to limiting sets"""
        # Only one region and two instances: one on-demand, other, reserved.
        # There are two apps and four time slots

        # Limit vms in both regions, and also cores in one region, for better
        # testing coverage
        amazon_dem = LimitingSet("Cloud1", name="Cloud1", max_vms=1)
        amazon_res = LimitingSet("CloudR", name="CloudR", max_vms=1, max_cores=4)

        # No limit for m3large (max_vms=0), for better testing coverage
        # This lack of limit does not make the problem feasible, due to the limiting_set
        m3large = InstanceClass(
            "m3large", name="m3large", limiting_sets=(amazon_dem,), max_vms=0, price=10,
            time_unit="h")
        m3large_r = InstanceClass(
            "m3large_r", name="m3large_r", limiting_sets=(amazon_res,), max_vms=20, price=7,
            time_unit="h", is_reserved=True)
        app0 = App("app0", name="Test app0")
        app1 = App("app1", name="Test app1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32, 30, 30),
                     time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194, 1003),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                m3large: {app0: 10, app1: 500},
                m3large_r: {app0: 10, app1: 500}
                })
            )

        problem_phase_i = Problem(
            id="example",
            name="Test problem",
            workloads=workloads,
            instance_classes=(m3large, m3large_r),
            performances=performances)

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32
        # to_yaml = util.problems_to_yaml({"p1": problem_phase_i})
        # with (open("test_data/problems/problem2.yaml", "w")) as output:
        #     output.write(to_yaml)

    def test_create_problem3_using_api(self):
        """Simple test (1region, 2inst, 2aps, 4timeslots), limits on cores"""
        # Only one region and two instances: one on-demand, other, reserved.
        # There are two apps and four time slots

        amazon_dem = LimitingSet("Cloud1", name="Cloud1", max_vms=20, max_cores=20)
        amazon_res = LimitingSet("CloudR", name="CloudR", max_vms=20, max_cores=10)

        m3large = InstanceClass(
            "m3large", name="m3large", limiting_sets=(amazon_dem,), max_vms=20, cores=2, price=10,
            time_unit="h")
        m3large_r = InstanceClass(
            "m3large_r", name="m3large_r", limiting_sets=(amazon_res,), max_vms=20, cores=4, price=7,
            time_unit="h", is_reserved=True)
        app0 = App("app0", name="Test app0")
        app1 = App("app1", name="Test app1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32, 30, 30),
                     time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194, 1003),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                m3large: {app0: 10, app1: 500},
                m3large_r: {app0: 10, app1: 500}
                })
            )
        problem_phase_i = Problem(
            id="example",
            name="Test problem",
            workloads=workloads,
            instance_classes=(m3large, m3large_r),
            performances=performances)

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32

        # to_yaml = util.problems_to_yaml({"p1": problem_phase_i})
        # with (open("test_data/problems/problem3.yaml", "w")) as output:
        #     output.write(to_yaml)




class TestProblemSolvingPhaseI(PresetProblemPaths):
    """Test solving phase I for feasible, unfeasible, integer_unfeasible, and too big problems
    for the allowed time"""

    def test_old_simple_case_one_region(self):
        max_instances = 20
        performance = 1000
        base_price = 100
        period_in_hours = 365*24
        region = LimitingSet("Cloud1", name="Cloud1", max_vms=max_instances)
        i0 = InstanceClass(
            "ondemand", name="On Demand", price=base_price, limiting_sets=(region,),
            max_vms=max_instances, is_reserved=False, time_unit="h")
        i1 = InstanceClass(
            "reserved", name="Reserved", price=0.8*base_price, limiting_sets=(region,),
            max_vms=max_instances, is_reserved=True, time_unit="h")
        app0 = App("App0", name="App0")
        workloads = (
            Workload("ltwp", description="Test", app=app0, values=(2*performance,)*period_in_hours,
                     time_unit="h"),
        )
        performances = PerformanceSet(
            id="perfs",
            time_unit="h",
            values=PerformanceValues({
                i0: {app0: performance},
                i1: {app0: performance}
            })
        )
        problem = Problem(
            id="example",
            name="PhaseI",
            workloads=workloads,
            instance_classes=(i0,i1),
            performances=performances
        )
        phaseI = phases.PhaseI(problem)

        solution = phaseI.solve()

        # Optimal cost of the solution should be 1401600
        assert solution.solving_stats.algorithm.status == Status.optimal
        assert solution.solving_stats.optimal_cost == 1401600

        # The number of reserved instances (i1) should be 2, for all apps
        assert solution.reserved_allocation.vms_number[0] == 2
        assert solution.reserved_allocation.instance_classes == (i1,)

        # The number of on-demand instances (i0) for app0, and workload index 0, should be 0
        workload_index = 0
        app0_index = solution.allocation.apps.index(app0)
        i0_index = solution.allocation.instance_classes.index(i0)
        assert (solution.allocation.values[workload_index][app0_index][i0_index]
                == 0)

        # These values should match the PuLP solution, still stored in MallooviaLp object
        # but this is not the intended way to get it, because it is implementation dependent
        assert phaseI._malloovia_lp.get_status() == Status.optimal
        assert phaseI._malloovia_lp.cooked.map_res[app0, i1].varValue == 2
        assert phaseI._malloovia_lp.cooked.map_dem[app0, i0, (2*performance,)].varValue == 0

    def test_read_problem1_and_solve_it(self):
        """Solve problem 1 which has optimal cost of 178"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem_phase_i = problems['example']

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32

        solution = phases.PhaseI(problem_phase_i).solve()

        # The solution is optimal, with cost 178
        assert solution.solving_stats.algorithm.status == Status.optimal
        assert solution.solving_stats.optimal_cost == 178

        # The solution uses all reserved instance classes
        reserved_instances = tuple(
            ins for ins in problem_phase_i.instance_classes if ins.is_reserved)
        assert (solution.reserved_allocation.instance_classes
                == reserved_instances)

        # The solution of this problem uses 3 reserved instances of the same VM
        # for each app so the reserved_allocation should be a tuple with a single
        # element (since there is a single reserved instance class), with value 6
        # (the sum for all apps)
        assert (solution.reserved_allocation.vms_number == (6,))

        # Check the histogram computed by MallooviaLp
        assert set(solution.allocation.repeats) == set((2,1,1))

    def test_read_infeasible_problem2_and_solve_it(self):
        """Solve problem2, which is infeasible"""
        problems = util.read_problems_from_yaml(self.problems["problem2"])
        assert "example" in problems
        problem_phase_i = problems['example']

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32

        phaseI = phases.PhaseI(problem_phase_i)
        solution = phaseI.solve()

        assert solution.solving_stats.algorithm.status == Status.infeasible

        # Trying to get the cost or the allocation should raise exception
        with pytest.raises(ValueError, match="not optimal"):
            phaseI._malloovia_lp.get_cost()

        with pytest.raises(ValueError, match="not optimal"):
            assert phaseI._malloovia_lp.get_allocation() is None

        with pytest.raises(ValueError, match="not optimal"):
            assert phaseI._malloovia_lp.get_reserved_allocation() is None

    def test_read_infeasible_problem2_and_solve_it_relaxed(self):
        """Solve problem2, which is infeasible even if relaxed"""
        problems = util.read_problems_from_yaml(self.problems["problem2"])
        assert "example" in problems
        problem_phase_i = problems['example']

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32

        phaseI = phases.PhaseI(problem_phase_i)
        phaseI.solve(relaxed=True)
        assert phaseI.solution.solving_stats.algorithm.status == Status.infeasible

        with pytest.raises(Exception, match="not optimal"):
            phaseI._malloovia_lp.get_cost()

        with pytest.raises(Exception, match="not optimal"):
            assert phaseI._malloovia_lp.get_allocation() is None

        with pytest.raises(Exception, match="not optimal"):
            assert phaseI._malloovia_lp.get_reserved_allocation() is None

    def test_read_problem3_and_solve_it(self):
        """Solve problem 3 which has optimal cost of 226"""
        problems = util.read_problems_from_yaml(self.problems["problem3"])
        assert "example" in problems
        problem_phase_i = problems['example']

        solution = phases.PhaseI(problem_phase_i).solve()
        assert solution.solving_stats.algorithm.status == Status.optimal
        assert solution.solving_stats.optimal_cost == 226

        # Check allocation is integer
        for row in solution.allocation.values:
            for app in row:
                for num in app:
                    assert round(num) == num

    def test_read_problem3_and_solve_it_relaxed(self):
        """Solve problem 3 in relaxed form which has optimal cost of 180"""
        problems = util.read_problems_from_yaml(self.problems["problem3"])
        assert "example" in problems
        problem_phase_i = problems['example']

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32

        solution = phases.PhaseI(problem_phase_i).solve(relaxed=True)
        assert solution.solving_stats.algorithm.status == Status.optimal
        assert solution.solving_stats.optimal_cost == 180

        # Check allocation is non integer
        for row in solution.allocation.values:
            for app in row:
                for num in app:
                    assert num == 0 or round(num) != num

    def test_abort_solver(self):
        """Solve one problem too big for the fixed maxSeconds"""
        problems = util.read_problems_from_yaml(self.problems["problem3"])
        assert "example" in problems
        problem_phase_i = problems['example']
        app0 = problem_phase_i.workloads[0].app
        app1 = problem_phase_i.workloads[1].app

        # Use larger workloads (200 timeslots, random values)
        workloads = (
            Workload("wl_app0", description="Test", app=app0, time_unit="h",
                    values=tuple(random.randint(25, 35) for i in range(200))),
            Workload("wl_app1", description="Test", app=app1, time_unit="h",
                    values=tuple(random.randint(990, 1200) for i in range(200)))
        )

        problem_phase_i = problem_phase_i._replace(workloads=workloads)

        # First solve it with time enough, to obtain the optimal solution
        solution = phases.PhaseI(problem_phase_i).solve(solver=COIN(maxSeconds=20))
        assert solution.solving_stats.algorithm.status == Status.optimal
        optimal_cost = solution.solving_stats.optimal_cost

        # Solve it again, but limit the time so that the solver is aborted
        solution = phases.PhaseI(problem_phase_i).solve(solver=COIN(maxSeconds=0.01))
        assert solution.solving_stats.algorithm.status == Status.aborted

        # When aborted, the optimal cost is not found
        assert solution.solving_stats.optimal_cost is None
        # But malloovia can give a lower bound
        assert solution.solving_stats.algorithm.lower_bound <= optimal_cost

    def test_unknown_error_in_pulp(self):
        """Load any problem and mock pulp so that it raises PulpError, to test
        if malloovia handles correctly the exception"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem_phase_i = problems['example']

        phaseI = phases.PhaseI(problem_phase_i)

        # We run solver inside a context which patches the PuLP method which
        # actually calls cbc. The patched version simply raises PulpSolverError
        # and we test that malloovia catches it and sets the correct status
        # optimal_cost and lower_bound
        with patch.object(COIN, "solve_CBC",
                        side_effect=PulpSolverError("Mocked error")):
            solution = phaseI.solve()
        assert solution.solving_stats.algorithm.status == Status.cbc_error
        assert solution.solving_stats.optimal_cost is None
        assert solution.solving_stats.algorithm.lower_bound is None

    def test_problem_with_undefined_solution(self):
        "Detect cbc returns '-3' error, which means integer infeasible"
        amazon_dem = LimitingSet("Cloud1", name="Cloud1", max_vms=20, max_cores=15)
        amazon_res = LimitingSet("CloudR", name="CloudR", max_vms=20, max_cores=10)
        m3large = InstanceClass(
            "m3large", name="m3large", limiting_sets=(amazon_dem,), max_vms=20, cores=4, price=10,
            time_unit="h")
        m3large_r = InstanceClass(
            "m3large_r", name="m3large_r", limiting_sets=(amazon_res,), max_vms=20, cores=4,
            price=7, time_unit="h", is_reserved=True)
        app0 = App("app0", "Test app0")
        app1 = App("app1", "Test app1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32, 30, 30),
                     time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194, 1003),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                m3large: {app0: 10, app1: 500},
                m3large_r: {app0: 10, app1: 500}
                })
            )
        problem = Problem(
            id="example",
            name="Test problem",
            workloads=workloads,
            instance_classes=(m3large, m3large_r),
            performances=performances)

        solution = phases.PhaseI(problem).solve()
        assert solution.solving_stats.algorithm.status == Status.integer_infeasible


class TestMallooviaLpApi(PresetProblemPaths):
    """Tests new malloovia API, by calling directly MallooviaLp() constructor instead of
    phases.PhaseI()"""

    def test_invalid_problem_missing_performance(self):
        limiting_set = LimitingSet("Cloud", name="Cloud", max_vms=20)
        instance = InstanceClass(
            "Instance", name="Instance", limiting_sets=(limiting_set,), price=10, max_vms=10,
            time_unit="h")
        app0 = App("App0", name="App0")
        app1 = App("App1", name="App1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32, 44), time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                instance: {app0: 10, },  # Missing app1 performance
                })
            )
        system = System(
            id="infr",
            name="Test problem",
            apps=(app0, app1),
            instance_classes=(instance,),
            performances=performances
        )

        with pytest.raises(KeyError):
            lp = lpsolver.MallooviaLp(system, workloads)

    def test_invalid_problem_missing_workload_value(self):
        limiting_set = LimitingSet("Cloud", name="Cloud", max_vms=20)
        instance = InstanceClass(
            "Instance", name="Instance", limiting_sets=(limiting_set,), price=10, max_vms=10,
            time_unit="h")
        app0 = App("App0", name="App0")
        app1 = App("App1", name="App1")
        workloads = (
            Workload("wl_app0", description="Test", app=app0, values=(30, 32,), time_unit="h"),
            Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194),
                     time_unit="h")
        )
        performances = PerformanceSet(
            id="test_perfs",
            time_unit="h",
            values=PerformanceValues({
                instance: {app0: 10, app1: 20},  # Missing app1 performance
                })
            )
        system = System(
            id="example",
            name="Test problem",
            apps=(app0, app1),
            instance_classes=(instance,),
            performances=performances
        )
        # The error is detected in the constructor
        with pytest.raises(AssertionError, match="All workloads should have the same length"):
            lp = lpsolver.MallooviaLp(system, workloads)

    def test_read_problem1_and_solve_it(self):
        """Solve problem 1 which has optimal cost of 178"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem_phase_i = problems['example']

        system = system_from_problem(problem_phase_i)
        lp = lpsolver.MallooviaLp(system, problem_phase_i.workloads)
        lp.create_problem()
        # Trying to access the solution before it was solved, raises ValueError
        assert lp.get_status() == Status.unsolved
        with pytest.raises(ValueError, match="not optimal"):
            lp.get_cost()
        with pytest.raises(ValueError, match="not optimal"):
            lp.get_allocation()
        with pytest.raises(ValueError, match="not optimal"):
            lp.get_reserved_allocation()

        lp.solve()
        assert lp.get_status() == Status.optimal
        reserved_allocation = lp.get_reserved_allocation()
        cost = lp.get_cost()

        assert cost == 178
        assert reserved_allocation.vms_number == (6,)

    def test_read_problem1_fixing_reserved_vms(self):
        """Solve problem 1, but forcing the number of reserved VMS"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem_phase_i = problems['example']
        rsv_instance = problem_phase_i.instance_classes[1]
        assert rsv_instance.is_reserved

        system = system_from_problem(problem_phase_i)

        # Use preallocation parameter to fix the total number of reserved instances to 4
        lp = lpsolver.MallooviaLp(
            system,
            problem_phase_i.workloads,
            preallocation=ReservedAllocation(
                instance_classes=(rsv_instance,),
                vms_number=(4,)
            )
        )

        lp.create_problem()
        lp.solve()
        reserved_allocation = lp.get_reserved_allocation()
        # Check that the solution has 4 reserved instances, as fixed
        assert reserved_allocation.vms_number == (4,)

        # The solution has to be more costly than the optimal in which we had 6 reserved
        cost = lp.get_cost()
        assert cost > 178

    def test_read_problem1_fixing_ondemand_vms(self):
        """Solve problem 1, but forcing the number of on-demand VMS. This is not useful
        in a real case, but Malloovia allows for it, and so this test covers that path."""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem_phase_i = problems['example']
        dem_instance = problem_phase_i.instance_classes[0]
        assert not dem_instance.is_reserved

        system = system_from_problem(problem_phase_i)

        # Use preallocation parameter to fix the total number of reserved instances to 4
        lp = lpsolver.MallooviaLp(
            system,
            problem_phase_i.workloads,
            preallocation=ReservedAllocation(
                instance_classes=(dem_instance,),
                vms_number=(4,)
            )
        )

        lp.create_problem()
        lp.solve()
        allocation = lp.get_allocation()
        # Check that the solution has 4 on-demand instances, for every timeslot as fixed
        for timeslot in allocation.values:
            assert sum(app_vms[1] for app_vms in timeslot) >= 4

        # The solution has to be more costly than the optimal in which we had 6 reserved
        cost = lp.get_cost()
        assert cost > 178

    def test_emulate_phase_ii(self):
        """Solve phaseI using malloovia and the full workload, then use malloovia again several
        times to emulate phase II, passing 1 timeslot at time"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        solution = phases.PhaseI(problem).solve()
        rsv_instances = solution.reserved_allocation.vms_number[0]
        assert rsv_instances == 6

        # Find out the index of the reserved instance in the solution allocation
        ondemand_index = None
        for i, iclass in enumerate(solution.allocation.instance_classes):
            if not iclass.is_reserved:
                ondemand_index = i
        assert ondemand_index is not None

        # Use it  to extract the number of on-demand VMs for each workload, per app
        on_demand_allocations_app0 = tuple(
            solution.allocation.values[t][0][ondemand_index]
            for t in range(len(solution.allocation.workload_tuples))
        )
        on_demand_allocations_app1 = tuple(
            solution.allocation.values[t][1][ondemand_index]
            for t in range(len(solution.allocation.workload_tuples))
        )

        assert on_demand_allocations_app0 == (0, 1, 0)
        assert on_demand_allocations_app1 == (0, 0, 0)

        app0, app1 = solution.allocation.apps
        system = system_from_problem(problem)

        # Emulate phase II
        for wl0, wl1 in zip(*(w.values for w in problem.workloads)):
            # For each (wl0,wl1) we build a new problem which has those values
            # as workload, and the remaining of the problem is identical
            # We also swap the order of the workloads, to test that MallooviaLp is robust
            # against this ordering (it should be invariant because each workload
            # includes an app field to relate it to the apps)
            workloads = (
                Workload("wl_app1", description="Test", app=app1, values=(wl1,), time_unit="h"),
                Workload("wl_app0", description="Test", app=app0, values=(wl0,), time_unit="h"),
            )

            # Solve this problem with malloovia. Since the workloads are composed of
            # a single value, this is equivalent to solve a single timeslot
            # If we fix to 6 the number of reserved instances, this emulates phaseII
            lp = lpsolver.MallooviaLp(
                system,
                workloads,
                preallocation=solution.reserved_allocation
                )
            lp.create_problem()
            lp.solve()

            # Check that the number of reserved instances matches those of phaseI
            rsv = lp.get_reserved_allocation()
            assert rsv.vms_number[0] == 6

            # Check that the full allocation also matches the phaseI solution for this
            # particular workload (it should match because we are using as STWP the same
            # sequence used as LTWP)
            full = lp.get_allocation()

            # Check that indexes match
            assert full.apps == solution.allocation.apps
            assert full.instance_classes == solution.allocation.instance_classes
            assert len(full.values) == 1

            # Check that allocation for this particular workload tuple matches
            # the one found in phaseII
            wl_index = solution.allocation.workload_tuples.index((wl0,wl1))
            assert  full.values[0] == solution.allocation.values[wl_index]



    def test_emulate_phase_ii_with_predictor(self):
        """Solve phaseI using malloovia and the full workload, then use malloovia again several
        times to emulate phase II, passing 1 timeslot at time, using Omniscient predictor"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        solution = phases.PhaseI(problem).solve()
        rsv_instances = solution.reserved_allocation.vms_number[0]
        assert rsv_instances == 6

        # Find out the index of the reserved instance in the solution allocation
        ondemand_index = None
        for i, iclass in enumerate(solution.allocation.instance_classes):
            if not iclass.is_reserved:
                ondemand_index = i
        assert ondemand_index is not None

        # Use it  to extract the number of on-demand VMs for each workload, per app
        on_demand_allocations_app0 = tuple(
            solution.allocation.values[t][0][ondemand_index]
            for t in range(len(solution.allocation.workload_tuples))
        )
        on_demand_allocations_app1 = tuple(
            solution.allocation.values[t][1][ondemand_index]
            for t in range(len(solution.allocation.workload_tuples))
        )

        assert on_demand_allocations_app0 == (0, 1, 0)
        assert on_demand_allocations_app1 == (0, 0, 0)

        app0, app1 = solution.allocation.apps
        system = system_from_problem(problem)

        # Emulate phase II
        predictor = phases.OmniscientSTWPredictor(problem.workloads)
        for workloads in predictor:
            # Solve this problem with malloovia. Since the workloads are composed of
            # a single value, this is equivalent to solve a single timeslot
            # If we fix to 6 the number of reserved instances, this emulates phaseII
            lp = lpsolver.MallooviaLp(
                system=system,
                workloads=workloads,
                preallocation=solution.reserved_allocation
                )
            lp.create_problem()
            lp.solve()

            # Check that the number of reserved instances matches those of phaseI
            rsv = lp.get_reserved_allocation()
            assert rsv.vms_number[0] == 6

            # Check that the full allocation also matches the phaseI solution for this
            # particular workload (it should match because we are using as STWP the same
            # sequence used as LTWP)
            full = lp.get_allocation()

            # Check that indexes match
            assert full.apps == solution.allocation.apps
            assert full.instance_classes == solution.allocation.instance_classes
            assert len(full.values) == 1

            # Check that allocation for this particular workload tuple matches
            # the one found in phaseII
            wl0 = workloads[0].values[0]
            wl1 = workloads[1].values[0]
            wl_index = solution.allocation.workload_tuples.index((wl0,wl1))
            assert  full.values[0] == solution.allocation.values[wl_index]

class TestPhaseII(PresetProblemPaths):
    def test_phase_ii_should_reject_infeasible_phase_i(self):
        """Trying to solve phase ii when phase i was infeasible should raise ValueError"""
        # Read problem2, which is infeasible
        problems = util.read_problems_from_yaml(self.problems["problem2"])
        assert "example" in problems
        problem_phase_i = problems['example']

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32

        phaseI = phases.PhaseI(problem_phase_i)
        solution = phaseI.solve()

        assert solution.solving_stats.algorithm.status == Status.infeasible

        with pytest.raises(ValueError, match="phase_i_solution passed to PhaseII is not optimal"):
            phaseII = phases.PhaseII(problem=problem_phase_i, phase_i_solution=solution)

    def test_phase_ii_complete(self):
        """Solve phaseI and phaseII"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        solution_i = phases.PhaseI(problem).solve()
        rsv_instances = solution_i.reserved_allocation.vms_number[0]
        assert rsv_instances == 6

        phase_ii = phases.PhaseII(
            problem=problem,
            phase_i_solution=solution_i
        )
        solution_ii = phase_ii.solve_period()

        timeslots = len(problem.workloads[0].values)
        assert solution_ii is not None
        assert len(solution_ii.allocation.values) == timeslots
        # The first and last timeslot have exactly the same workload,
        # so they should have exactly the same solution
        assert (solution_ii.allocation.values[0]
                is solution_ii.allocation.values[-1])

        # Since we used the same STWP than LTWP, each timeslot should
        # have the same allocation than in phaseI
        for wl_tupl, alloc in zip(solution_ii.allocation.workload_tuples,
                                solution_ii.allocation.values):
            phase_i_index = solution_i.allocation.workload_tuples.index(wl_tupl)
            phase_i_alloc = solution_i.allocation.values[phase_i_index]
            assert phase_i_alloc == alloc

        # Also both solution should have the same cost
        assert (solution_ii.global_solving_stats.optimal_cost
                == solution_i.solving_stats.optimal_cost)

    def test_phase_ii_with_unfeasible_timeslots(self):
        """Solves phaseI and then uses for phase II a different STWP which causes
        unfeasible timeslots"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        solution_i = phases.PhaseI(problem).solve()
        rsv_instances = solution_i.reserved_allocation.vms_number[0]
        assert rsv_instances == 6

        # Create a phase_ii_problem from phase I problem, replacing
        # the workload for a new one which has a very high load for app0 at
        # timeslot 1, which will cause that timeslot to be infeasible
        app0, app1 = (wl.app for wl in problem.workloads)
        phase_ii_problem = problem._replace(
            workloads = (
                Workload("wl_app0", description="Test", app=app0, values=(30, 270, 30, 30),
                         time_unit="h"),
                Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194, 1003),
                         time_unit="h")
            )
        )

        phase_ii = phases.PhaseII(
            problem=phase_ii_problem,
            phase_i_solution=solution_i
        )
        solution_ii = phase_ii.solve_period()
        assert solution_ii.global_solving_stats.status == Status.overfull

        timeslots = len(problem.workloads[0].values)
        assert solution_ii is not None
        assert len(solution_ii.allocation.values) == timeslots
        # The first and last timeslot have exactly the same workload,
        # so they should have exactly the same solution
        assert (solution_ii.allocation.values[0]
                is solution_ii.allocation.values[-1])

        # Timeslot 1 is overfull
        assert solution_ii.solving_stats[1].algorithm.status == Status.overfull
        # The overfull timeslot has a solution with cost 242
        assert solution_ii.solving_stats[1].optimal_cost == 242
        # And assigns 4 reserved an 20 on demand instances to app0
        assert solution_ii.allocation.values[1][0] == [4, 20]

        # The global solution is more costly, as much as the solution
        # for the overfull timeslot

class TestPhaseIIGuided(PresetProblemPaths):
    def test_phase_ii_should_reject_infeasible_phase_i(self):
        """Trying to solve phase ii when phase i was infeasible should raise ValueError"""
        # Read problem2, which is infeasible
        problems = util.read_problems_from_yaml(self.problems["problem2"])
        assert "example" in problems
        problem_phase_i = problems['example']

        # Some trivial checks
        assert problem_phase_i.performances.values.get_by_ids('m3large', 'app0') == 10
        assert problem_phase_i.workloads[0].values[1] == 32

        phaseI = phases.PhaseI(problem_phase_i)
        solution = phaseI.solve()

        assert solution.solving_stats.algorithm.status == Status.infeasible

        with pytest.raises(ValueError, match="phase_i_solution passed to PhaseII is not optimal"):
            phaseII = phases.PhaseIIGuided(problem=problem_phase_i, phase_i_solution=solution)

    def test_phase_ii_complete(self):
        """Solve phaseI and phaseII"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        solution_i = phases.PhaseI(problem).solve()
        rsv_instances = solution_i.reserved_allocation.vms_number[0]
        assert rsv_instances == 6

        phase_ii = phases.PhaseIIGuided(
            problem=problem,
            phase_i_solution=solution_i
        )
        solution_ii = phase_ii.solve_period()

        timeslots = len(problem.workloads[0].values)
        assert solution_ii is not None
        assert len(solution_ii.allocation.values) == timeslots
        # The first and last timeslot have exactly the same workload,
        # so they should have exactly the same solution
        assert (solution_ii.allocation.values[0]
                is solution_ii.allocation.values[-1])

        # Since we used the same STWP than LTWP, each timeslot should
        # have the same allocation than in phaseI
        for wl_tupl, alloc in zip(solution_ii.allocation.workload_tuples,
                                solution_ii.allocation.values):
            phase_i_index = solution_i.allocation.workload_tuples.index(wl_tupl)
            phase_i_alloc = solution_i.allocation.values[phase_i_index]
            assert phase_i_alloc == alloc

        # Also both solution should have the same cost
        assert (solution_ii.global_solving_stats.optimal_cost
                == solution_i.solving_stats.optimal_cost)

    def test_phase_ii_by_timeslot(self):
        """Solve phaseI and phaseII using solve_timeslot() repeatdly"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        solution_i = phases.PhaseI(problem).solve()
        rsv_instances = solution_i.reserved_allocation.vms_number[0]
        assert rsv_instances == 6

        phase_ii = phases.PhaseIIGuided(
            problem=problem,
            phase_i_solution=solution_i
        )

        predictor = phases.OmniscientSTWPredictor(problem.workloads)
        
        solutions = []
        for workloads in predictor: 
            solutions.append(phase_ii.solve_timeslot(workloads=workloads))

        solution_ii = phase_ii._aggregate_solutions(solutions)

        timeslots = len(problem.workloads[0].values)
        assert solution_ii is not None
        assert len(solution_ii.allocation.values) == timeslots
        # The first and last timeslot have exactly the same workload,
        # so they should have exactly the same solution
        assert (solution_ii.allocation.values[0]
                is solution_ii.allocation.values[-1])

        # Since we used the same STWP than LTWP, each timeslot should
        # have the same allocation than in phaseI
        for wl_tupl, alloc in zip(solution_ii.allocation.workload_tuples,
                                solution_ii.allocation.values):
            phase_i_index = solution_i.allocation.workload_tuples.index(wl_tupl)
            phase_i_alloc = solution_i.allocation.values[phase_i_index]
            assert phase_i_alloc == alloc

        # Also both solution should have the same cost
        assert (solution_ii.global_solving_stats.optimal_cost
                == solution_i.solving_stats.optimal_cost)

    def test_phase_ii_single_timeslot_minimum_on_demand(self):
        """Solve phaseI and phaseII using solve_timeslot() and fixing minimum on-demand VMs"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        solution_i = phases.PhaseI(problem).solve()
        rsv_instances = solution_i.reserved_allocation.vms_number[0]
        assert rsv_instances == 6

        phase_ii = phases.PhaseIIGuided(
            problem=problem,
            phase_i_solution=solution_i
        )

        predictor = phases.OmniscientSTWPredictor(problem.workloads)
       
        ondemand_ics = [ic for ic in problem.instance_classes if not ic.is_reserved]
        ondemand_preallocation = ReservedAllocation((ondemand_ics[0],), (3,)) # At least 3
        workloads = list(predictor)[0] 

        sol_timeslot = phase_ii.solve_timeslot(workloads=workloads,
                                               preallocation=ondemand_preallocation)
        assert sol_timeslot.reserved_allocation.vms_number[0] == 6
        alloc = sol_timeslot.allocation.values[0]
        assert alloc[0][0] + alloc[1][0] == 6   # Reserved
        assert alloc[0][1] + alloc[1][1] == 3   # ondemand


    def test_phase_ii_with_unfeasible_timeslots(self):
        """Solves phaseI and then uses for phase II a different STWP which causes
        unfeasible timeslots"""
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        solution_i = phases.PhaseI(problem).solve()
        rsv_instances = solution_i.reserved_allocation.vms_number[0]
        assert rsv_instances == 6

        # Create a phase_ii_problem from phase I problem, replacing
        # the workload for a new one which has a very high load for app0 at
        # timeslot 1, which will cause that timeslot to be infeasible
        app0, app1 = (wl.app for wl in problem.workloads)
        phase_ii_problem = problem._replace(
            workloads = (
                Workload("wl_app0", description="Test", app=app0, values=(30, 270, 30, 30),
                         time_unit="h"),
                Workload("wl_app1", description="Test", app=app1, values=(1003, 1200, 1194, 1003),
                         time_unit="h")
            )
        )

        phase_ii = phases.PhaseIIGuided(
            problem=phase_ii_problem,
            phase_i_solution=solution_i
        )
        solution_ii = phase_ii.solve_period()
        assert solution_ii.global_solving_stats.status == Status.overfull

        timeslots = len(problem.workloads[0].values)
        assert solution_ii is not None
        assert len(solution_ii.allocation.values) == timeslots
        # The first and last timeslot have exactly the same workload,
        # so they should have exactly the same solution
        assert (solution_ii.allocation.values[0]
                is solution_ii.allocation.values[-1])

        # Timeslot 1 is overfull
        assert solution_ii.solving_stats[1].algorithm.status == Status.overfull
        # The overfull timeslot has a solution with cost 242
        assert solution_ii.solving_stats[1].optimal_cost == 242
        # And assigns 4 reserved an 20 on demand instances to app0
        assert solution_ii.allocation.values[1][0] == [4, 20]

        # The global solution is more costly, as much as the solution
        # for the overfull timeslot

class TestModelClasses(PresetProblemPaths):

    def test_MallooviaHistogram(self):
        hist = MallooviaHistogram({
            (10, 10): 2,
            (10, 20): 1,
            (20, 20): 3
        })
        assert isinstance(hist, dict)
        assert hist[(10, 10)] == 2
        assert hist[(10, 20)] == 1
        assert hist[(20, 20)] == 3
        assert hist[(30, 30)] == 0
        assert str(hist) == "MallooviaHistogram with 3 values"

    def test_PerformanceValues(self):
        instances = [InstanceClass(id="ic%d"%i, name=None, limiting_sets=None, max_vms=0, 
                                   price=1, time_unit="h")
                     for i in range(3)]
        apps = [App(id="app%d"%i, name="App %d" % i)
                for i in range(2)]
        values = PerformanceValues({
            ic: {app: i*len(apps)+j for j, app in enumerate(apps)}
            for i, ic in enumerate(instances)
        })
        # Check the stored data
        assert (str(values) ==
                "PerformanceValues for ({} instance_classes x {} apps)"
                .format(len(instances), len(apps))
        )

        for i, (ic, app, value) in enumerate(values):
            assert ic in instances
            assert app in apps
            assert value == i

        # Test __eq__ method for PerformanceValues
        values_copy = copy.deepcopy(values)
        assert values == values_copy
        assert values != 0

    def test_Allocation_functions(self):
        # Read a problem to get instance class data
        problems = util.read_problems_from_yaml(self.problems["problem1"])
        assert "example" in problems
        problem = problems['example']

        sol_i = phases.PhaseI(problem).solve()

        allocation = sol_i.allocation
        assert allocation.repeats == [2, 1, 1]

        # The function allows both an allocation or a solution as input
        costs = compute_allocation_cost(allocation)
        assert costs.units == "cost"
        assert costs.values == [[[21.0, 0.0], [21.0, 0.0]],
                                [[21.0, 10.0], [21.0, 0.0]],
                                [[21.0, 0.0], [21.0, 0.0]]]

        costs = compute_allocation_cost(sol_i)
        assert costs.units == "cost"
        assert costs.values == [[[21.0, 0.0], [21.0, 0.0]],
                                [[21.0, 10.0], [21.0, 0.0]],
                                [[21.0, 0.0], [21.0, 0.0]]]

        # For the performances, the input can be a solution or the pair
        # allocation plus performance values
        perfs = compute_allocation_performance(allocation, problem.performances.values)
        assert perfs.units == "rph"
        assert perfs.values == [[[30.0, 0.0], [1500.0, 0.0]],
                                [[30.0, 10.0], [1500.0, 0.0]],
                                [[30.0, 0.0], [1500.0, 0.0]]]

        perfs = compute_allocation_performance(sol_i)
        assert perfs.units == "rph"
        assert perfs.values == [[[30.0, 0.0], [1500.0, 0.0]],
                                [[30.0, 10.0], [1500.0, 0.0]],
                                [[30.0, 0.0], [1500.0, 0.0]]]
