"Test the command line interface"
import os

from click.testing import CliRunner

from malloovia import cli
from .datapaths import PresetDataPaths

# pylint: disable=invalid-name

class TestCliModule(PresetDataPaths):
    """Test the command line interface"""
    def test_validate_valid_problem(self):
        """Test that the command line interface can validate a valid problem"""

        filename = self.get_problem("problem1.yaml")

        runner = CliRunner()
        result = runner.invoke(cli.cli, ['validate', filename])

        assert result.exit_code == 0
        assert "is correct" in result.output

    def test_validate_invalid_problem(self):
        """Test that the command line interface can validate an invalid problem"""

        filename = self.get_invalid("problem_with_numbers_as_names.yaml")

        runner = CliRunner()
        result = runner.invoke(cli.cli, ['validate', filename])

        assert result.exit_code == 0
        assert "does not validate" in result.output

    def test_solve_only_phase_i(self):
        """Test that the command line interface can solve only phase I"""

        filename = self.get_problem("problem1.yaml")

        runner = CliRunner()
        result = runner.invoke(cli.cli, ['solve', filename, '--phase-i-id', 'example'])

        assert result.exit_code == 0
        assert "Writing solutions" in result.output
        
        # The command saves the solution in problem1-sol.yaml by default
        os.remove('{}-sol.yaml'.format(filename[:-5]))

    def test_solve_phase_i_and_ii(self):
        """Test that the command line interface can solve phase I and II"""

        filename = self.get_problem("problem1.yaml")

        runner = CliRunner()
        result = runner.invoke(cli.cli, ['solve', filename, '--phase-i-id', 'example',
                                         '--phase-ii-id', 'example'])

        assert result.exit_code == 0
        assert "Writing solutions" in result.output

        # The command saves the solution in problem1-sol.yaml by default
        os.remove('{}-sol.yaml'.format(filename[:-5]))
