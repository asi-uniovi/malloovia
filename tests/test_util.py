"Tests for util.read_problem_from_yaml() and model.Performances"
import pytest
import yaml
from jsonschema import validate

from malloovia import util
from malloovia import phases
from malloovia.solution_model import Status
from .datapaths import PresetDataPaths

# pylint: disable=invalid-name

class TestUtilModule(PresetDataPaths):
    def test_yaml_back_and_forth_is_the_same(self):
        """Test the writer for the advanced yaml format, by reading it back"""
        # Read one example problem with YAML and get all the info as nested python dicts
        filename = self.get_valid("problem_example.yaml")
        with open(filename) as f:
            orig_raw_data = yaml.safe_load(f)

        # Convert those dicts to Malloovia classes
        problems = util.problems_from_dict(orig_raw_data, yaml_filename=filename)
        # Get the Yaml representation of Malloovia problems
        generated_yaml = util.problems_to_yaml(problems)
        # Convert it back to python dicts and those to Malloovia classes
        back_to_problems = util.problems_from_dict(yaml.safe_load(generated_yaml),
                                                yaml_filename=filename)
        # Compare malloovia classes to ensure that they store the same information in the
        # problem originally read from disk, and in the one generated by util.problems_to_yaml()
        assert problems == back_to_problems

    def test_read_problem_with_external_workload(self):
        """Reads a yaml file which specifies a problem and uses 'filename' property of the
        workload to reference an external file, instead of having the list of numbers in the yaml"""
        filename = self.get_valid("problem_example_external_workload.yaml")
        prob = util.read_problems_from_yaml(filename)
        assert prob['phaseI'].workloads[0].filename == "external_workload.csv"
        assert isinstance(prob['phaseI'].workloads[0].values, tuple)
        assert isinstance(prob['phaseI'].workloads[0].values[0], float)
        assert prob['phaseI'].workloads[0].values == prob['phaseI'].workloads[1].values
        assert prob['phaseI'].workloads[0].values == (20.0, 12.0, 5.0, 6.0, 15.0, 4.0, 3.0)

    def test_convert_to_yaml_problem_with_external_workload(self):
        """Reads a yaml file which uses the `filename` property of the workload to reference an
        external file, converts the problem back to yaml and checks that the result also uses the
        `filename` property and does not contain a `values` property."""

        filename = self.get_valid("problem_example_external_workload.yaml")
        prob = util.read_problems_from_yaml(filename)
        generated_yaml = util.problems_to_yaml(prob)
        raw_data = yaml.safe_load(generated_yaml)
        assert "filename" in raw_data['Workloads'][0]
        assert  raw_data['Workloads'][0]['filename'] == 'external_workload.csv'
        assert "values" not in raw_data['Workloads'][0]

    def test_solution_i_to_yaml(self):
        """Reads problem1, solves first phase it and dumps the solution, which is validated
        against malloovia schema"""
        problems = util.read_problems_from_yaml(self.get_problem("problem1.yaml"))
        assert "example" in problems
        problem_phase_i = problems['example']

        sol_i = phases.PhaseI(problem_phase_i).solve()
        assert sol_i.solving_stats.algorithm.status == Status.optimal
        assert sol_i.solving_stats.optimal_cost == 178

        sol_i_yaml = util.solutions_to_yaml([sol_i])
        sol_i_dict = yaml.safe_load(sol_i_yaml)
        with open(self.get_schema("malloovia.schema.yaml")) as file:
            sol_schema = yaml.safe_load(file)
        validate(sol_i_dict, sol_schema)

    def test_solution_ii_to_yaml(self):
        """Reads problem1, solves second phase and dumps the solution, which is validated
        against malloovia schema"""
        problems = util.read_problems_from_yaml(self.get_problem("problem1.yaml"))
        assert "example" in problems
        problem_phase_i = problems['example']

        sol_i = phases.PhaseI(problem_phase_i).solve()
        assert sol_i.solving_stats.algorithm.status == Status.optimal
        assert sol_i.solving_stats.optimal_cost == 178

        sol_ii = phases.PhaseII(problem_phase_i, sol_i).solve_period()
        assert sol_ii.global_solving_stats.status == Status.optimal
        assert sol_ii.global_solving_stats.optimal_cost == 178

        # It is neccessary to dump both solutions, because phase ii contains
        # a reference to the solution of phase i
        sol_ii_yaml = util.solutions_to_yaml([sol_i, sol_ii])
        sol_ii_dict = yaml.safe_load(sol_ii_yaml)
        with open(self.get_schema("malloovia.schema.yaml")) as file:
            sol_schema = yaml.safe_load(file)
        validate(sol_ii_dict, sol_schema)

    def test_read_from_github(self):
        problems = util.read_problems_from_github("problem1")
        assert len(problems) == 1
        problem = list(problems.values())[0]
        assert len(problem.instance_classes) == 2
        assert len(problem.workloads) == 2
        assert problem.workloads[0].values == (30, 32, 30, 30)
        assert problem.workloads[1].values == (1003, 1200, 1194, 1003)
