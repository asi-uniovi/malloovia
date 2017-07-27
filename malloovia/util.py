"""Utility functions to save and load Malloovia problem definitions"""

from typing import (Mapping, Sequence, Tuple, Union, Any, List)
import os.path
import urllib.request
import yaml

from .model import (
    App, LimitingSet, InstanceClass,
    Workload, PerformanceSet, PerformanceValues, Problem
)
from .solution_model import (
    SolutionI, SolutionII, SolvingStats, GlobalSolvingStats,
    AllocationInfo, ReservedAllocation
)


def read_problems_from_yaml(filename: str) -> Mapping[str, Problem]:
    """Reads the problem(s) definition from a YAML file.

    Args:
       filename: name of the YAML file to read.

    Returns:
        A dictionary whose keys are problem ids, and the values are :class:`Problem` objects.
    """
    with open(filename) as stream:
        data = yaml.safe_load(stream)
    return problems_from_dict(data, filename)

def read_problems_from_github(dataset: str, id: str = None,
                              base_url: str = None) -> Union[Problem, Mapping[str, Problem]]:
    """Reads a problem or set of problems from a GitHub repository.

    Args:
        dataset: the name of the yaml file which contains the set of problems,
            without extension.
        id: the id of the particular problem to load, if omitted all problems
            are read and a dictionary is returned, whose keys are problem ids
            and the values are the :class:`Problem` instances.
        base_url: the url to the folder where the file is stored. If None,
            it will read from https://raw.githubusercontent.com/asi-uniovi/malloovia/master/tests/test_data/problems/

    Returns:
        A dictionary whose keys are problem ids, and the values are
        :class:`Problem` objects, or a single :class:`Problem` if the
        id is passed as argument.
    """

    if base_url is None:
        base_url = ("https://raw.githubusercontent.com/asi-uniovi/malloovia"
                     "/master/tests/test_data/problems/")
    url = "{}/{}.yaml".format(base_url, dataset)
    with urllib.request.urlopen(url) as stream:
        data = yaml.safe_load(stream)
    problems = problems_from_dict(data, dataset)
    if id is None:
        return problems
    else:
        return problems[id]

def problems_from_dict(data: Mapping[str, Any], yaml_filename: str) -> Mapping[str, Problem]:
    """Takes data from a dictionary with a particular structure, and stores it in
    several Problem instances.

    Args:
        data: a dictionary which is the result of reading a YAML file. The dictionary
            is expected to have a particular structure. It can be previously validated
            through a YAML schema to ensure so.
    Returns:
        A dictionary whose keys are problem ids, and the values are :class:`Problem` objects.
    """
    # Mapping to remember which dictionaries were already converted to objects
    # Keys are ids of dictionaries,  values are the corresponding objects
    ids_to_objects = {}

    def create_if_neccesary(_class, _dict):
        """Auxiliar function to instantiate a new object from a dict only
        if the same dict was not already instantiated"""
        # If already created, return the stored object
        if id(_dict) in ids_to_objects:
            return ids_to_objects[id(_dict)]

        # If _dict is not a dict, it is an already created object, return it
        if not isinstance(_dict, dict):
            return _dict

        # Else, create the object, store it and return it
        new = _class(**_dict)
        ids_to_objects[id(_dict)] = new
        return new

    def copy_id_to_name(_dict):
        """Helper function to set the name equal to id, if missing"""
        if isinstance(_dict, dict) and "name" not in _dict:
            _dict["name"] = _dict["id"]

    def create_instance_classes(_list):
        """Helper functions which creates all required Instance_classes from
        a list of InstanceClasses, and theLimiting_sets referenced from
        those Instance_classes"""
        for ic_data in _list:
            copy_id_to_name(ic_data)
            limiting_sets = []
            for lset_data in ic_data["limiting_sets"]:
                copy_id_to_name(lset_data)
                limiting_sets.append(create_if_neccesary(LimitingSet,
                                                         lset_data))
            ic_data["limiting_sets"] = tuple(limiting_sets)
            create_if_neccesary(InstanceClass, ic_data)

    def create_workloads(_list):
        """Helper function which creates all  required Workloads from a list
        of workloads, and the Apps referenced from those workloads"""
        for w_data in _list:
            w_data["app"] = create_if_neccesary(App, w_data["app"])
            if w_data.get("filename"):
                values = read_from_relative_csv(filename=w_data["filename"],
                                                relative_to=yaml_filename)
            else:
                values = tuple(w_data["values"])
            w_data.update(values=values)
            create_if_neccesary(Workload, w_data)

    def create_performances(_dict):
        """Helper function which creates a Performances object from a list
        of performance dictionaries whose keys are instance_classes and apps"""
        # Check if this set of performances was already converted to
        # a Performances object, and reuse it
        if id(_dict) in ids_to_objects:
            return ids_to_objects[id(_dict)]

        # Else, create a dictionary suited for Performances constructor
        _list = _dict["values"]
        perf_dict = {}
        for p_data in _list:
            # Get references to instance_class and app objects. Hence all
            # required instance types and apps were already created by now,
            # their ids should be present in ids_to_objects.
            # Otherwise it would be a internal error, and an exception
            #  will be raised
            ic_object = ids_to_objects[id(p_data["instance_class"])]
            app_object = ids_to_objects[id(p_data["app"])]
            value = p_data["value"]
            if ic_object not in perf_dict:
                perf_dict[ic_object] = {}
            perf_dict[ic_object][app_object] = float(value)
        perf = PerformanceSet(id=_dict["id"], values=PerformanceValues(perf_dict))
        ids_to_objects[id(_dict)] = perf
        return perf

    # The main program only instantiates problems, and the other objects
    # referenced from those problems
    problems = {}

    # First pass: traverse all problems to ensure that all ics and apps
    # referenced from the problems are converted to namedtuples
    for problem in data["Problems"]:
        create_instance_classes(problem["instance_classes"])
        create_workloads(problem["workloads"])

    # Now traverse again to create the performances and problems
    for problem in data["Problems"]:
        performances = create_performances(problem["performances"])
        problem.update(
            workloads=tuple(ids_to_objects[id(w)]
                            for w in problem["workloads"]),
            instance_classes=tuple(ids_to_objects[id(i)]
                                   for i in problem["instance_classes"]),
            performances=performances
        )
        new_problem = Problem(**problem)
        problems[new_problem.id] = new_problem
    return problems

def problems_to_yaml(problems: Mapping[str, Problem]) -> str:     # pylint: disable=too-many-locals
    """Converts problems from the classes used by malloovia to a yaml string.

    Arguments:
        problems: it is a dictionary whose keys are the ids of the problems, and the values are
            instances of :class:`Problem`, which indirectly contains the full specification
            of the system, apps, workloads and performances, through references to other classes
    Returns:
        A string with a yaml representation of the problem and all the data associated with it.
        The YAML contains separate fields for "Apps", "Workloads", "Limiting_sets",
        "Instance_classes", "Performances" and "Problems", each one containing a list of apps,
        workloads, etc. respectively. These lists are dynamically built and contains the entities
        which are directly or indirectly referenced from the dict of problems received as input.

    The generated yaml contains internal anchors (automatically generated from the ids of the
    objects) and yaml references to those anchors, so that when the yaml is parsed back to python,
    the resulting dict contains internal references (instead of copies) to other dicts.
    """

    def collect_instance_classes_and_limiting_sets(problem):  # pylint: disable=invalid-name
        """Populates and returns instance_classes and limiting_sets sets"""
        instance_classes = set()
        limiting_sets = set()
        for i_c in problem.instance_classes:
            instance_classes.add(i_c)
            limiting_sets.update(set(i_c.limiting_sets))
        return instance_classes, limiting_sets

    def collect_workloads_and_apps(problem):
        """Populates and returns workloads and apps sets"""
        workloads = set()
        apps = set()
        for wld in problem.workloads:
            workloads.add(wld)
            apps.add(wld.app)
        return workloads, apps

    def collect_performances(problem):
        """Populates and returns performances set"""
        performances = set()
        performances.add(problem.performances)
        return performances


    def lsets_to_yaml(limiting_sets):
        """Returns an array of lines to add to the yaml array, representing the
        Limiting_sets part"""
        lines = []
        lines.append("Limiting_sets:")
        for l_s in sorted(limiting_sets):
            lines.append("  - &{}".format(l_s.id))
            lines.extend(_namedtuple_to_yaml(l_s, level=2))
        lines.append("")
        return lines

    def iclasses_to_yaml(instance_classes):
        """Returns an array of lines to add to the yaml array, representing the
        Instance_classes part"""
        lines = []
        lines.append("Instance_classes:")
        for i_c in sorted(instance_classes):
            aux = i_c._replace(
                limiting_sets="[{}]".format(
                    ", ".join("*{}".format(ls.id) for ls in i_c.limiting_sets)
                ))
            lines.append("  - &{}".format(aux.id))
            lines.extend(_namedtuple_to_yaml(aux, level=2))
        lines.append("")
        return lines

    def apps_to_yaml(apps):
        """Returns an array of lines to add to the yaml array, representing the
        Apps part"""
        lines = []
        lines.append("Apps:")
        for app in sorted(apps):
            lines.append("  - &{}".format(app.id))
            lines.extend(_namedtuple_to_yaml(app, level=2))
        lines.append("")
        return lines

    def wloads_to_yaml(workloads):
        """Returns an array of lines to add to the yaml array, representing the
        Workloads part"""
        lines = []
        # It is neccesary to remove "filename" if it is None, or "values" if not
        # But fields cannot be removed from namedtuples, so we convert it to dict
        lines.append("Workloads:")
        for w_l in sorted(workloads):
            aux = w_l._asdict()
            if aux["filename"]:
                aux.pop("values")
            else:
                aux.pop("filename")
                aux.update(values=list(w_l.values))
            aux.update(app="*{}".format(w_l.app.id))
            lines.append("  - &{}".format(aux["id"]))
            lines.extend(_dict_to_yaml(aux, level=2))
        lines.append("")
        return lines

    def probs_to_yaml(problems):
        """Returns an array of lines to add to the yaml array, representing the
        Problems part"""
        lines = []
        lines.append("Problems:")
        for prob in problems.values():
            aux = prob._replace(
                instance_classes="[{}]".format(
                    ", ".join("*{}".format(ic.id) for ic in prob.instance_classes)),
                workloads="[{}]".format(
                    ", ".join("*{}".format(wl.id) for wl in prob.workloads)),
                performances="*{}".format(prob.performances.id)
                )
            lines.append("  - &{}".format(aux.id))
            lines.extend(_namedtuple_to_yaml(aux, level=2))
        lines.append("")
        return lines

    def perfs_to_yaml(performances):
        """Returns an array of lines to add to the yaml array, representing the
        Performances part"""
        lines = []
        lines.append("Performances:")
        for perfset in sorted(performances):
            lines.append("  - &{}".format(perfset.id))
            lines.append("    id: {}".format(perfset.id))
            lines.append("    values:")
            for iclass, app, perf in perfset.values:
                lines.append("      - instance_class: *{}".format(iclass.id))
                lines.append("        app: *{}".format(app.id))
                lines.append("        value: {}".format(perf))
        return lines

    # "main" body of the function
    yam = []                  # Lisf of lines of the resulting yaml
    apps = set()              # set of App objects indirectly referenced from the problems
                              #   (via the workloads)
    workloads = set()         # set of Workload objects directly referenced from the problems
    limiting_sets = set()     # set of Limiting_set objects indirectly referenced from the problems
                              #  (via instance classes)
    instance_classes = set()  # set of Instance_class objects directly referenced from the problems
    performances = set()      # set of Performance objects directly referenced from the problem

    for prob in problems.values():
        _wls, _apps = collect_workloads_and_apps(prob)
        _ics, _ls = collect_instance_classes_and_limiting_sets(prob)
        apps.update(_apps)
        workloads.update(_wls)
        limiting_sets.update(_ls)
        instance_classes.update(_ics)
    for prob in problems.values():
        performances.update(collect_performances(prob))

    yam.extend(lsets_to_yaml(limiting_sets))
    yam.extend(iclasses_to_yaml(instance_classes))
    yam.extend(apps_to_yaml(apps))
    yam.extend(wloads_to_yaml(workloads))
    yam.extend(perfs_to_yaml(performances))
    yam.extend(probs_to_yaml(problems))
    return "\n".join(yam)

def preprocess_yaml(input_yaml_filename: str) -> str:
    """Reads a YAML file and "expands" the ``Problems_from_file`` section.

    Args:
        input_yaml_filename: name of the yaml file to read
    Returns:
        A string containing the contents read from the file, but without the section
        ``Problems_from_file`` which was replaced by the contents of the file referenced
        in that section. This name is considered relative to the path of the main yaml file.
    """

    output = []
    with open(input_yaml_filename) as istream:
        for line in istream:
            if line.startswith("Problems_from_file"):
                filename = line.split(":")[1].strip()
                line = read_file_relative_to(filename=filename, relative_to=input_yaml_filename)
            output.append(line)
    return "".join(output)

def read_file_relative_to(filename: str, relative_to:str) -> str:
    """Reads one file by its name, considered relative to other filename.

    Arguments:
        filename: the name of the file to read
        relative_to: the name of the file to which the first one is considered relative

    Examples:
        * ``read_file_relative_to("foo/bar/whatever.txt", "other.txt")``
            will read the file at ``"foo/bar/other.txt"``
        * ``read_file_relative_to("foo/bar/whatever.txt", "../other.txt")``
            will read the file at ``"foo/other.txt"``

    Returns:
        The whole content of the file, as a string.

    Raises:
        FileNotFoundError: If the file is not found.
    """
    path_to_input = os.path.abspath(relative_to)
    path_to_filename = os.path.join(os.path.dirname(path_to_input), filename)
    return open(path_to_filename).read()

def read_from_relative_csv(filename: str, relative_to:str) -> Tuple[float]:
    """Reads and parses the content of one file, given its name considered relative to other filename.

    The file is first read by :func:`read_file_relative_to()` and the contents are assumed
    to be a sequence of floating numbers, one per line.

    Arguments:
        filename: the name of the file to read
        relative_to: the name of the file to which the first one is considered relative

    Returns:
        The sequence of read floating numbers, as a tuple.

    Raises:
        FileNotFoundError: If the file is not found.
    """
    content = read_file_relative_to(filename, relative_to)
    return tuple(float(line) for line in content.split("\n") if line)

def solutions_to_yaml(solutions: Sequence[Union[SolutionI, SolutionII]]) -> str:
    """Converts a list of solutions to a YAML string.

    Arguments:
        solutions: list of solutions to convert, each one can be a
            :class:`SolutionI` or a :class:`SolutionII`.
    Returns:
        A string with a YAML representation of the solution and the
        associated problem. The YAML uses anchors and references
        to tie up the different parts.
    """
    def solution_i_to_yaml(sol: SolutionI) -> List[str]:
        """Converts a SolutionI to a yaml string"""
        lines = []
        lines.extend((
            "- &{}".format(sol.id),
            "  id: {}".format(sol.id),
            "  problem: *{}".format(sol.problem.id),
        ))
        lines.append("  solving_stats:")
        lines.extend(solving_stats_to_yaml(sol.solving_stats, level=2))
        lines.append("  reserved_allocation:")
        lines.extend(reserved_allocation_to_yaml(sol.reserved_allocation, level=2))
        lines.append("  allocation:")
        lines.extend(allocation_to_yaml(sol.allocation, level=2))
        return lines

    def solution_ii_to_yaml(sol: SolutionII) -> List[str]:
        """Converts a SolutionII to a yaml string"""
        lines = []
        lines.extend((
            "- &{}".format(sol.id),
            "  id: {}".format(sol.id),
            "  problem: *{}".format(sol.problem.id),
            "  previous_phase: *{}".format(sol.previous_phase.id),
        ))

        lines.append("  global_solving_stats:")
        lines.extend(global_solving_stats_to_yaml(
            sol.global_solving_stats, level=2))

        lines.append("  solving_stats:")
        for i, stats in enumerate(sol.solving_stats):
            lines.append("    - # {} -> {}".format(
                i, sol.allocation.workload_tuples[i]
            ))
            lines.extend(solving_stats_to_yaml(stats, level=3))

        lines.append("  allocation:")
        lines.extend(allocation_to_yaml(sol.allocation, level=2))
        return lines

    def solving_stats_to_yaml(stats: SolvingStats, level: int) -> List[str]:
        lines = []
        tab = "  "*level
        lines.extend((
            "{}creation_time: {}".format(tab, stats.creation_time),
            "{}solving_time: {}".format(tab, stats.solving_time),
            "{}optimal_cost: {}".format(tab, stats.optimal_cost),
            "{}algorithm:".format(tab),
            "  {}malloovia:".format(tab),
        ))
        lines.extend(_namedtuple_to_yaml(stats.algorithm, level=level+2))
        return lines

    def global_solving_stats_to_yaml(stats: GlobalSolvingStats,
                                     level: int) -> List[str]:
        lines = []
        tab = "  "*level
        lines.extend((
            "{}creation_time: {}".format(tab, stats.creation_time),
            "{}solving_time: {}".format(tab, stats.solving_time),
            "{}optimal_cost: {}".format(tab, stats.optimal_cost),
            "{}status: {}".format(tab, stats.status.name),
        ))
        return lines


    def reserved_allocation_to_yaml(rsv: ReservedAllocation,
                                    level: int) -> List[str]:
        lines = []
        tab = "  "*level
        lines.extend((
            "{}instance_classes: [{}]".format(tab, list_of_references_to_yaml(rsv.instance_classes)),
            "{}vms_number: [{}]".format(tab, ", ".join(str(v) for v in rsv.vms_number)),
        ))
        return lines

    def list_of_references_to_yaml(lst: Sequence[Any]) -> str:
        return ", ".join("*{}".format(element.id) for element in lst)

    def list_to_yaml(lst: Sequence[Any]) -> str:
        return ", ".join(str(element) for element in lst)

    def allocation_to_yaml(alloc: AllocationInfo, level: int) -> List[str]:
        lines = []
        tab = "  "*level
        lines.extend((
            "{}instance_classes: [{}]".format(tab, list_of_references_to_yaml(alloc.instance_classes)),
            "{}apps: [{}]".format(tab, list_of_references_to_yaml(alloc.apps)),
            "{}workload_tuples: [{}]".format(tab, list_to_yaml(list(wl) for wl in alloc.workload_tuples)),
            # "{}repeats: [{}]".format(tab, list_to_yaml(alloc.repeats)),
            "{}vms_number:".format(tab),
        ))
        for i, t_alloc in enumerate(alloc.values):
            lines.append("  {}- # {} -> {}".format(
                tab, i, alloc.workload_tuples[i]
            ))
            for app_alloc in t_alloc:
                lines.append("    {}- [{}]".format(tab, app_alloc))
        return lines


    # First collect al problems referenced in the solutions
    problems = set()
    for solution in solutions:
        problems.add(solution.problem)
    # Convert those problems to yaml
    lines = []
    lines.append(problems_to_yaml({p.id: p for p in problems}))

    # Now convert each solution
    lines.append("Solutions:")
    for solution in solutions:
        if isinstance(solution, SolutionI):
            lines.extend(solution_i_to_yaml(solution))
        elif isinstance(solution, SolutionII):
            lines.extend(solution_ii_to_yaml(solution))
        else:
            raise ValueError(
                "Solution({}) is of unknown type {}"
                .format(solution.id, type(solution))
                )
    return "\n".join(lines)


def _namedtuple_to_yaml(data, level=2):
    """Converts to yaml any namedtuple, via dict.

    Arguments:
        data: the namedtuple to convert
        level: the indentation level

    Returns:
        array of lines to add to yaml array
    """
    return _dict_to_yaml(data._asdict(), level)

def _dict_to_yaml(data, level):
    """Converts to yaml any dictionary, by iterating through its keys and values.

    Arguments:
        data: the dict to convert
        level: the indentation level

    Returns:
        array of lines to add to yaml array
    """
    lines = []
    for key, value in data.items():
        if value is None:
            value = 'null'
        if hasattr(value, "name"):  # For Enums
            value = value.name
        lines.append("{}{}: {}".format("  "*level, key, value))
    return lines


__all__ = [
    'read_problems_from_yaml', 'read_problems_from_github',
    'problems_to_yaml', 'solutions_to_yaml'
]