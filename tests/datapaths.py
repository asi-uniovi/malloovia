"""Module to set the correct paths for the data files used in tests"""
import os
import malloovia

class PresetDataPaths:
    """This class computes the absolute path to the test data and the
    malloovia schemas, so that the tests can use it"""
    def setup(self):
        self.path_to_problems = os.path.join(os.path.dirname(__file__), "test_data", "problems")
        self.path_to_valid = os.path.join(os.path.dirname(__file__), "test_data", "valid")
        self.path_to_invalid = os.path.join(os.path.dirname(__file__), "test_data", "invalid")
        self.path_to_schema = os.path.join(os.path.dirname(malloovia.__file__))

    def get_valid(self, filename):
        """Returns the absolute path of a valid example"""
        return os.path.join(self.path_to_valid, filename)
    def get_invalid(self, filename):
        """Returns the absolute path of an invalid example"""
        return os.path.join(self.path_to_invalid, filename)
    def get_schema(self, filename):
        """Returns the absolute path of a schema"""
        return os.path.join(self.path_to_schema, filename)
    def get_problem(self, filename):
        """Returns the absolute path of an example problem"""
        return os.path.join(self.path_to_problems, filename)