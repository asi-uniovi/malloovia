# Run this file with nosetest or pytest
"""Tests for the validation of schemas an yaml examples"""

import ruamel.yaml
import os
import pytest
from jsonschema import (validate, Draft4Validator, exceptions)
from malloovia import util
from .datapaths import PresetDataPaths

yaml = ruamel.yaml.YAML(typ='safe')
yaml.safe_load = yaml.load


# pylint: disable=invalid-name

class TestValidateSchemas(PresetDataPaths):
    # First validate the schemas themselves
    def test_validate_malloovia_schema_against_meta_schema(self):
        """Validates malloovia.schema"""
        schema = yaml.safe_load(open(self.get_schema("malloovia.schema.yaml")))
        Draft4Validator.check_schema(schema)




class TestValidateExamples(PresetDataPaths):
    # Next validate different yaml files against the schemas

    def test_problem_against_malloovia_schema(self):
        """Validates (valid) example problem against malloovia schema"""
        yaml_schema = yaml.safe_load(open(self.get_schema("malloovia.schema.yaml")))
        data = yaml.safe_load(open(self.get_valid("problem_example.yaml")))
        validate(data, yaml_schema)

    def test_validate_problem_with_external_workload_against_malloovia_schema(self):
        """Validates a (valid) problem which uses workload from a external file.
        It cannot validate if the referenced file indeed exists (the loader will do that)"""
        yaml_schema = yaml.safe_load(open(self.get_schema("malloovia.schema.yaml")))
        data = yaml.safe_load(open(self.get_valid("problem_example_external_workload.yaml")))
        validate(data, yaml_schema)

    def test_problems_plus_solutions_example_against_malloovia_schema(self):
        """Validates (valid) yaml file which contains both some problems and their
        solutions in the same file"""
        yaml_schema = yaml.safe_load(open(self.get_schema("malloovia.schema.yaml")))
        data = yaml.safe_load(open(self.get_valid("problems_plus_solutions_example.yaml")))
        validate(data, yaml_schema)

    def test_solutions_imports_problem_against_malloovia_schema(self):
        """Validates (valid) yaml file which contains the solution to some problems and a
        reference to the file in which the problems are defined"""

        # This kind of YAML file cannot be validated, nor read, because the references
        # from the solution to the problem cannot be resolved, unless the problem is
        # in the same file. So a preprocessing is required to include the problems
        # in the same yaml string than the solutions
        yaml_schema = yaml.safe_load(open(self.get_schema("malloovia.schema.yaml")))
        full = util.preprocess_yaml(self.get_valid("solution_example.yaml"))
        data = yaml.safe_load(full)
        validate(data, yaml_schema)


    def test_solution_with_full_phase_i_allocation(self):
        """Validates (valid) yaml file which stores the full solution of phaseI, which is
        optional since only the reserved_allocation is required"""
        yaml_schema = yaml.safe_load(open(self.get_schema("malloovia.schema.yaml")))
        full = util.preprocess_yaml(self.get_valid("solution_with_full_phase_I_allocation.yaml"))
        data = yaml.safe_load(full)
        validate(data, yaml_schema)

    # Test some invalid files

    def test_invalid_solution_without_problem(self):
        """Validates an invalid yaml file which contains the solution to some problems but
        does not include the problem definition nor the reference to an external file"""

        # This case in fact cannot be validated because it cannot be load, because the
        # references to the problem entities cannot be solved
        full = util.preprocess_yaml(self.get_invalid("solution_without_problem.yaml"))
        with pytest.raises(ruamel.yaml.composer.ComposerError, match="undefined alias"):
            data = yaml.safe_load(full)

    def test_invalid_problem_numbers_as_names(self):
        """Validates an invalid yaml file with the definition of a problem which uses
        numbers as names for some entities"""
        full = util.preprocess_yaml(self.get_invalid("problem_with_numbers_as_names.yaml"))
        yaml_schema = yaml.safe_load(open(self.get_schema("malloovia.schema.yaml")))
        data = yaml.safe_load(full)
        with pytest.raises(exceptions.ValidationError):
            validate(data, yaml_schema)
