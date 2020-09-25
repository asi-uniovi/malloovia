"""Testing malloovia hybrid model"""
from typing import Tuple
import pytest  # type: ignore
import ruamel.yaml
from jsonschema import validate
from pulp import COIN, PulpSolverError  # type: ignore

yaml = ruamel.yaml.YAML(typ="safe")
yaml.safe_load = yaml.load


from malloovia.model import (
    LimitingSet,
    InstanceClass,
    App, 
    Workload,
    Problem,
    PerformanceSet,
    PerformanceValues,
    system_from_problem,
)
from malloovia import util
from malloovia import phases
from malloovia.solution_model import (
    SolutionI, Status,
    ReservedAllocation,
    AllocationInfo,
    MallooviaHistogram,
    compute_allocation_cost,
    compute_allocation_performance,
)
from malloovia import lpsolver
from .datapaths import PresetDataPaths

def create_problem():
    # Malloovia's classic limiting sets, one public, another private
    r1 = LimitingSet("r1", name="us-east-1", max_vms=20)
    r2 = LimitingSet("r2", name="private-limits", max_cores=20)
    m3large = InstanceClass(
            "m3large",
            name="m3large",
            limiting_sets=(r1,),
            max_vms=20,
            price=10,
            time_unit="h",
        )
    m3large_r = InstanceClass(
            "m3large_r",
            name="m3large_r",
            limiting_sets=(r1,),
            max_vms=20,
            price=7,
            time_unit="h",
            is_reserved=True,
        )
    m3priv = InstanceClass(
        "m3large_priv",
        name="m3large_priv",
        limiting_sets=(r2,),
        max_vms=20,
        price=1,
        cores=5,
        time_unit="h",
        is_private=True,
        is_reserved=True
    )
    m3priv2 = InstanceClass(
        "m3xlarge_priv",
        name="m3xlarge_priv",
        limiting_sets=(r2,),
        max_vms=20,
        price=1,
        cores=10,
        time_unit="h",
        is_private=True,
        is_reserved=True
    )
    app0 = App("app0", name="Test app0")
    app1 = App("app1", name="Test app1")
    workloads = (
        Workload(
            "wl_app0",
            description="Test",
            app=app0,
            values=(100, 120, 100, 100),
            time_unit="h",
        ),
        Workload(
            "wl_app1",
            description="Test",
            app=app1,
            values=(1003, 1200, 1194, 1003),
            time_unit="h",
        ),
    )
    performances = PerformanceSet(
        id="test_perfs",
        time_unit="h",
        values=PerformanceValues(
            {m3large: {app0: 10, app1: 500}, m3large_r: {app0: 10, app1: 500},
            m3priv: {app0: 9, app1: 450},
            m3priv2: {app0: 25, app1: 1000}}
        ),
    )
    problem_phase_i = Problem(
        id="example",
        name="Example hybrid cloud",
        workloads=workloads,
        instance_classes=(m3large, m3large_r, m3priv, m3priv2),
        performances=performances,
    )
    return problem_phase_i

class TestExampleProblem:

    def test_solve_problem_with_private_constraints(self):
        """This test creates and solves one problem in which the private cloud
        imposes limits on the maximum number of cores"""
        problem = create_problem()
        phase_i = phases.PhaseI(problem)
        solution = phase_i.solve()
        assert solution.solving_stats.algorithm.status == Status.optimal

        # The cost of the optimal solution has to be 252.0 for this problem
        assert solution.solving_stats.optimal_cost == 252.0

        # There is a single private limiting set
        private_limiting_sets = set(ls  
            for ic in problem.instance_classes if ic.is_private
            for ls in ic.limiting_sets)
        assert len(private_limiting_sets) == 1
        private_limiting_set = list(private_limiting_sets)[0]

        # That limiting set imposes a limit in the number of cores
        max_cores = private_limiting_set.max_cores
        assert max_cores == 20

        # The solution does not violate the max_cores limit
        used_cores = []
        for ts_alloc in solution.allocation.values:
            used_cores_in_ts = 0
            for app_alloc in ts_alloc:
                for i, ic_number in enumerate(app_alloc):
                    ic = solution.allocation.instance_classes[i]
                    if ic.is_private:
                        used_cores_in_ts += ic_number * ic.cores
            used_cores.append(used_cores_in_ts)

        assert all(n_cores <= max_cores for n_cores in used_cores)

class TestStorageYaml:

    def test_problem_with_private_to_yaml(self):
        """Creates a problem which uses private instances, converts it to YAML,
        checks that the resulting YAML is valid, and finally reads it back
        to Python and compares it with the initial problem"""
        problem = create_problem()

        # Create yaml version
        from malloovia import util
        yaml_str = util.problems_to_yaml({"Example hybrid cloud": problem})
        # Optionally write it actually to disk, to visually inspect it
        # with open("/tmp/test.yaml", "w") as f:
        #    f.write(yaml_str)

        # Check that the generated problem is valid against the schema      
        problem_data = yaml.safe_load(yaml_str)
        malloovia_schema = util.get_schema()
        try:
            validate(problem_data, malloovia_schema)
        except Exception as e:
            pytest.fail("The generated yaml is not valid against the schema")

        # The actual test is to read it back      
        back_to_problems = util.problems_from_dict(
            yaml.safe_load(yaml_str), yaml_filename="Nofile"
        )
        # Compare malloovia classes to ensure that they store the same information in the
        # original problem.
        assert problem == back_to_problems["example"]      

    def test_solution_with_hybrid_to_yaml_back_and_forth(self):
        """Creates and solves a problem which uses private instances, 
        converts the solution to YAML, checks that the resulting YAML
        is valid, and finally reads it back to Python and compares it
        with the solution object"""        
        problem = create_problem()
        solution = phases.PhaseI(problem).solve()

        # Dump solution to yaml
        from malloovia import util
        yaml_str = util.solutions_to_yaml([solution])
        with open("/tmp/test.yaml", "w") as f:
            f.write(yaml_str)
        
        # Check that the generated solution is valid against the schema      
        solution_data = yaml.safe_load(yaml_str)
        malloovia_schema = util.get_schema()
        try:
            validate(solution_data, malloovia_schema)
        except Exception as e:
            pytest.fail("The generated yaml is not valid against the schema")

        # The actual test is to read it back      
        back_to_solution = util.solutions_from_dict(
            yaml.safe_load(yaml_str), yaml_filename="Nofile"
        )
        # Compare malloovia classes to ensure that they store the same information in the
        # original problem.
        assert solution == back_to_solution['solution_i_example']

