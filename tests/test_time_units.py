"Tests for time units in malloovia"
import pytest
# import ruamel.yaml
# from jsonschema import validate

# from malloovia import util
# from malloovia import phases
# from malloovia.solution_model import Status, SolvingStats, SolutionI, MallooviaStats
# from .datapaths import PresetDataPaths

# yaml = ruamel.yaml.YAML(typ='safe')
# yaml.safe_load = yaml.load

from malloovia.model import TimeUnit

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
