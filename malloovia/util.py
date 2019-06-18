"""Utility functions to save and load Malloovia problem definitions"""

from typing import (
    Mapping,
    Dict,
    Sequence,
    Tuple,
    Union,
    Any,
    List,
    Set,
    Iterable,
)
from functools import lru_cache
import os.path
import gzip
import re
import urllib.request

# To use ruamel.yaml instead of pyyaml:
from ruamel.yaml import YAML  # type: ignore

yaml = YAML(typ="safe")
yaml.safe_load = yaml.load

from .model import (
    App,
    LimitingSet,
    InstanceClass,
    Workload,
    PerformanceSet,
    PerformanceValues,
    Problem,
)
from .solution_model import (
    SolutionI,
    SolutionII,
    SolvingStats,
    MallooviaStats,
    GlobalSolvingStats,
    AllocationInfo,
    ReservedAllocation,
    Status,
)

MallooviaObjectModel = Union[
    App,
    LimitingSet,
    InstanceClass,
    Workload,
    PerformanceSet,
    Problem,
    SolutionI,
    SolutionII,
]

def _sanitize(_id: str) -> str:
    """Sanitizes a string to use it as part of a YAML anchor.
    It allows only for alphanumeric characters, and all the others
    are replaced by underscore."""

    return re.sub("[^0-9a-zA-Z_]+", "_", _id)


def _anchor_from_id(obj: MallooviaObjectModel) -> str:
    """Given one Malloovia object, generate a valid YAML anchor by
    combining the internal ``obj.i``, sanitized by replacing every
    non-ascii letter or digit by ``_``, and appending an hexedecimal
    string derived from the internal Python ``id`` of the object.LimitingSet
    
    Args:
        obj: Malloovia object (NamedTuple)

    Returns:
        A string to be used as anchor
    """

    # Special handling of SolutionI and SolutionII objects
    # since these objects contain fields of type List, and
    # thus they are not hashable, as required by lru_cache
    if type(obj) in [SolutionI, SolutionII]:
        return "{}_{}".format(_sanitize(obj.id), hex(id(obj)))

    # For any other case, delegate to the cached version
    return __anchor_from_id_cached(obj)

@lru_cache(maxsize=None)
def __anchor_from_id_cached(obj: MallooviaObjectModel) -> str:
    if "id" in obj._fields:
        _id = _sanitize(obj.id)     # type: ignore
    else:
        # Some Malloovia object doesn't have an id field
        # Use an empty string in this case
        _id = ""
    return "{}_{}".format(_id, hex(id(obj)))

def read_problems_from_yaml(filename: str) -> Mapping[str, Problem]:
    """Reads the problem(s) definition from a YAML file.

    Args:
       filename: name of the YAML file to read, it has to have the extension
          ``.yaml`` or ``.yaml.gz`` (which is automatically decompressed on read).

    Returns:
        A dictionary whose keys are problem ids, and the values are :class:`Problem` objects.

    Raises:
        ValueError if the file has not the expected extension.
    """
    _open = _get_open_function_from_extension(filename)

    with _open(filename, mode="rt", encoding="utf8") as stream:
        data = yaml.safe_load(stream)
    return problems_from_dict(data, filename)


def read_problems_from_github(
    dataset: str, _id: str = None, base_url: str = None
) -> Union[Problem, Mapping[str, Problem]]:
    """Reads a problem or set of problems from a GitHub repository.

    Args:
        dataset: the name of the yaml file which contains the set of problems,
            without extension.
        id: the id of the particular problem to load, if omitted all problems
            are read and a dictionary is returned, whose keys are problem ids
            and the values are the :class:`Problem` instances.
        base_url: the url to the folder where the file is stored. If None,
            it will read from
            https://raw.githubusercontent.com/asi-uniovi/malloovia/master/tests/test_data/problems/

    Returns:
        A dictionary whose keys are problem ids, and the values are
        :class:`Problem` objects, or a single :class:`Problem` if the
        id is passed as argument.
    """

    if base_url is None:
        base_url = (
            "https://raw.githubusercontent.com/asi-uniovi/malloovia"
            "/units/tests/test_data/problems/"
        )

    url = "{}/{}.yaml".format(base_url, dataset)
    with urllib.request.urlopen(url) as stream:
        data = yaml.safe_load(stream)

    problems = problems_from_dict(data, dataset)

    if _id is None:
        return problems

    return problems[_id]


def problems_from_dict(
    data: Mapping[str, Any], yaml_filename: str
) -> Mapping[str, Problem]:
    """Takes data from a dictionary with a particular structure, and stores it in
    several Problem instances.

    Args:
        data: a dictionary which is the result of reading a YAML file. The dictionary
            is expected to have a particular structure. It can be previously validated
            through a YAML schema to ensure so.
    Returns:
        A dictionary whose keys are problem ids, and the values are :class:`Problem` objects.
    """
    problems, _ = _problems_and_ids_from_dict(data, yaml_filename)
    return problems


def _problems_and_ids_from_dict(
    data: Mapping[str, Any], yaml_filename: str
) -> Tuple[Mapping[str, Problem], Dict[Any, Any]]:
    """Takes data from a dictionary with a particular structure, and stores it in
    several Problem instances. It also returns another dictionary that can be used to
    translate between YAML ids and the corresponding objects.

    Args:
        data: a dictionary which is the result of reading a YAML file. The dictionary
            is expected to have a particular structure. It can be previously validated
            through a YAML schema to ensure so.
    Returns:
        A tuple with two values:
        - A dictionary whose keys are problem ids, and the values are :class:`Problem` objects.
        - A dictionary whose keys are YAML ids, and the values are the corresponding
        malloovia object
    """

    # Mapping to remember which dictionaries were already converted to objects
    # Keys are object ids of dictionaries, values are the corresponding malloovia objects
    ids_to_objects: Dict[int, Any] = {}

    def create_if_neccesary(_class, _dict):
        """Auxiliary function to instantiate a new object from a dict only
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
        """Helper function which creates all required Instance_classes from
        a list of InstanceClasses, and the Limiting_sets referenced from
        those Instance_classes"""
        for ic_data in _list:
            copy_id_to_name(ic_data)
            limiting_sets = []
            for lset_data in ic_data["limiting_sets"]:
                copy_id_to_name(lset_data)
                limiting_sets.append(create_if_neccesary(LimitingSet, lset_data))
            ic_data["limiting_sets"] = tuple(limiting_sets)
            create_if_neccesary(InstanceClass, ic_data)

    def create_workloads(_list):
        """Helper function which creates all required Workloads from a list
        of workloads, and the Apps referenced from those workloads"""
        for w_data in _list:
            w_data["app"] = create_if_neccesary(App, w_data["app"])
            if w_data.get("filename"):
                values = read_from_relative_csv(
                    filename=w_data["filename"], relative_to=yaml_filename
                )
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
            # will be raised
            ic_object = ids_to_objects[id(p_data["instance_class"])]
            app_object = ids_to_objects[id(p_data["app"])]
            value = p_data["value"]
            if ic_object not in perf_dict:
                perf_dict[ic_object] = {}
            perf_dict[ic_object][app_object] = float(value)
        perf = PerformanceSet(
            id=_dict["id"],
            values=PerformanceValues(perf_dict),
            time_unit=_dict["time_unit"],
        )
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
            workloads=tuple(ids_to_objects[id(w)] for w in problem["workloads"]),
            instance_classes=tuple(
                ids_to_objects[id(i)] for i in problem["instance_classes"]
            ),
            performances=performances,
        )
        new_problem = Problem(**problem)
        problems[new_problem.id] = new_problem
        ids_to_objects[id(problem)] = new_problem
    return problems, ids_to_objects


def read_solutions_from_yaml(
    filename: str
) -> Mapping[str, Union[SolutionI, SolutionII]]:
    """Reads the solutions(s) contained in a YAML file.

    Args:
       filename: name of the YAML file to read, it has to have the extension
          ``.yaml`` or ``.yaml.gz`` (which is automatically decompressed on read).

    Returns:
        A dictionary whose keys are solution ids, and the values are :class:`Solution` objects.

    Raises:
        ValueError if the file has not the expected extension.
    """
    _open = _get_open_function_from_extension(filename)

    with _open(filename, mode="rt", encoding="utf8") as stream:
        data = yaml.safe_load(stream)
    return solutions_from_dict(data, filename)


def solutions_from_dict(
    data: Mapping[str, Any], yaml_filename: str
) -> Mapping[str, Union[SolutionI, SolutionII]]:
    """Takes data from a dictionary with a particular structure, and stores it in
    several Solution instances.

    Args:
        data: a dictionary which is the result of reading a YAML file. The dictionary
            is expected to have a particular structure. It can be previously validated
            through a YAML schema to ensure so.
    Returns:
        A dictionary whose keys are solution ids, and the values are :class:`Solution` objects.
    """

    # Mapping to remember which dictionaries were already converted to objects
    # Keys are object ids of dictionaries, values are the corresponding malloovia objects
    ids_to_objects: Dict[int, Any] = {}

    def _is_phase_i_solution(solution_dict):
        """Receives a solution as a dict generated by yaml_load() and returns
        true if is a phase I solution and false otherwise"""
        if not "previous_phase" in solution_dict:
            return True

        return False

    def _create_phase_i_solution(solution_dict):
        return SolutionI(**solution_dict)

    def _create_phase_ii_solution(solution_dict):
        solution_dict["previous_phase"] = ids_to_objects[
            id(solution_dict["previous_phase"])
        ]
        return SolutionII(**solution_dict)

    def _dict_list_to_id_list(dict_list):
        id_list = []
        for item in dict_list:
            id_list.append(ids_to_objects[id(item)])
        return id_list

    def _convert_allocation(solution_dict):
        alloc = solution_dict["allocation"]
        alloc["apps"] = tuple(_dict_list_to_id_list(alloc["apps"]))
        alloc["instance_classes"] = tuple(_dict_list_to_id_list(alloc["instance_classes"]))
        alloc["values"] = alloc.pop("vms_number")
        alloc["values"] = tuple(
            tuple(tuple(vms) for vms in app) for app in alloc["values"]
        )
        if "units" not in alloc:
            alloc["units"] = "vms"
        if "workload_tuples" not in alloc:
            alloc["workload_tuples"] = tuple()
        else:
            alloc["workload_tuples"] = list(tuple(wl) for wl in alloc["workload_tuples"])
        solution_dict["allocation"] = AllocationInfo(**alloc)

    def _convert_reserved_allocation(solution_dict):
        alloc = solution_dict["reserved_allocation"]
        alloc["instance_classes"] = tuple(_dict_list_to_id_list(alloc["instance_classes"]))
        alloc["vms_number"] = tuple(alloc["vms_number"])
        solution_dict["reserved_allocation"] = ReservedAllocation(**alloc)

    def _status_to_enum(status: str) -> Status:
        status_enum = Status.__members__.get(status)
        if status_enum is None:
            raise ValueError("Invalid status '{}' in solving_stats".format(status))
        return status_enum

    def _convert_malloovia_stats(data: Dict[str, Any]) -> MallooviaStats:
        status = data["status"]
        data["status"] = _status_to_enum(status)
        return MallooviaStats(**data)

    def _convert_solving_stats(solving_stats: Dict[str, Any]) -> SolvingStats:
        alg_stats = solving_stats.get("algorithm")
        if alg_stats and alg_stats.get("malloovia"):
            solving_stats["algorithm"] = _convert_malloovia_stats(alg_stats.get("malloovia"))
        return SolvingStats(**solving_stats)


    def _convert_solving_stats_phase_i(solution_dict):
        solving_stats = solution_dict.get("solving_stats")
        if solving_stats:
            solution_dict["solving_stats"] = _convert_solving_stats(solving_stats)

    def _convert_malloovia_stats_phase_ii(solution_dict):
        solving_stats = solution_dict.get("solving_stats")
        if solving_stats:
            result = []
            for stats in solving_stats:
                result.append(_convert_solving_stats(stats))
            solution_dict["solving_stats"] = result

    def _convert_global_solving_stats(solution_dict):
        g_solving_stats = solution_dict.get("global_solving_stats")
        if g_solving_stats:
            status = g_solving_stats["status"]
            g_solving_stats["status"] = _status_to_enum(status)
            solution_dict["global_solving_stats"] = GlobalSolvingStats(**g_solving_stats)

    def _create_solution(solution_dict):
        solution_dict["problem"] = ids_to_objects[id(solution_dict["problem"])]

        if "allocation" in solution_dict:
            _convert_allocation(solution_dict)
           
        if _is_phase_i_solution(solution_dict):
            _convert_solving_stats_phase_i(solution_dict)
            _convert_reserved_allocation(solution_dict)
            result = _create_phase_i_solution(solution_dict)
        else:
            _convert_malloovia_stats_phase_ii(solution_dict)
            _convert_global_solving_stats(solution_dict)
            result = _create_phase_ii_solution(solution_dict)

        ids_to_objects[id(solution_dict)] = result
        return result

    _, ids_to_objects = _problems_and_ids_from_dict(data, yaml_filename)

    solutions = {}

    # Create solutions for phase I. They have to be created before solutions for
    # phase II because the latter reference the former
    for solution_dict in data["Solutions"]:
        if _is_phase_i_solution(solution_dict):
            solution = _create_solution(solution_dict)
            solutions[solution.id] = solution

    # Create solutions for phase II
    for solution_dict in data["Solutions"]:
        if not _is_phase_i_solution(solution_dict):
            solution = _create_solution(solution_dict)
            solutions[solution.id] = solution

    return solutions


def problems_to_yaml(
    problems: Mapping[str, Problem]
) -> str:  # pylint: disable=too-many-locals
    """Converts problems from the classes used by malloovia to a yaml string.

    Args:
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

    def collect_instance_classes_and_limiting_sets(
        problem
    ):  # pylint: disable=invalid-name
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
            lines.append("  - &{}".format(_anchor_from_id(l_s)))
            lines.extend(_namedtuple_to_yaml(l_s, level=2))
        lines.append("")
        return lines

    def iclasses_to_yaml(instance_classes):
        """Returns an array of lines to add to the yaml array, representing the
        Instance_classes part"""
        lines = []
        lines.append("Instance_classes:")
        for i_c in sorted(instance_classes):
            anchor = _anchor_from_id(i_c)
            aux = i_c._replace(
                limiting_sets="[{}]".format(
                    ", ".join("*{}".format(_anchor_from_id(ls)) for ls in i_c.limiting_sets)
                )
            )
            lines.append("  - &{}".format(anchor))
            lines.extend(_namedtuple_to_yaml(aux, level=2))
        lines.append("")
        return lines

    def apps_to_yaml(apps):
        """Returns an array of lines to add to the yaml array, representing the
        Apps part"""
        lines = []
        lines.append("Apps:")
        for app in sorted(apps):
            lines.append("  - &{}".format(_anchor_from_id(app)))
            lines.extend(_namedtuple_to_yaml(app, level=2))
        lines.append("")
        return lines

    def wloads_to_yaml(workloads):
        """Returns an array of lines to add to the yaml array, representing the
        Workloads part"""
        lines = []
        # It is necessary to remove "filename" if it is None, or "values" if not
        # But fields cannot be removed from namedtuples, so we convert it to dict
        lines.append("Workloads:")
        for w_l in sorted(workloads):
            anchor = _anchor_from_id(w_l)
            aux = w_l._asdict()
            if aux["filename"]:
                aux.pop("values")
            else:
                aux.pop("filename")
                aux.update(values=list(w_l.values))
            aux.update(app="*{}".format(_anchor_from_id(w_l.app)))
            lines.append("  - &{}".format(anchor))
            lines.extend(_dict_to_yaml(aux, level=2))
        lines.append("")
        return lines

    def probs_to_yaml(problems):
        """Returns an array of lines to add to the yaml array, representing the
        Problems part"""
        lines = []
        lines.append("Problems:")
        for prob in problems.values():
            anchor = _anchor_from_id(prob)
            aux = prob._replace(
                instance_classes="[{}]".format(
                    ", ".join("*{}".format(_anchor_from_id(ic)) for ic in prob.instance_classes)
                ),
                workloads="[{}]".format(
                    ", ".join("*{}".format(_anchor_from_id(wl)) for wl in prob.workloads)
                ),
                performances="*{}".format(_anchor_from_id(prob.performances)),
            )
            lines.append("  - &{}".format(anchor))
            lines.extend(_namedtuple_to_yaml(aux, level=2))
        lines.append("")
        return lines

    def perfs_to_yaml(performances):
        """Returns an array of lines to add to the yaml array, representing the
        Performances part"""
        lines = []
        lines.append("Performances:")
        for perfset in sorted(performances):
            lines.append("  - &{}".format(_anchor_from_id(perfset)))
            lines.append("    id: {}".format(perfset.id))
            lines.append("    time_unit: {}".format(perfset.time_unit))
            lines.append("    values:")
            for iclass, app, perf in perfset.values:
                lines.append("      - instance_class: *{}".format(_anchor_from_id(iclass)))
                lines.append("        app: *{}".format(_anchor_from_id(app)))
                lines.append("        value: {}".format(perf))
        return lines

    # "main" body of the function
    yam: List[str] = []  # List of lines of the resulting yaml
    apps: Set[App] = set()  # set of App objects indirectly referenced from the problems
    #   (via the workloads)
    workloads: Set[
        Workload
    ] = set()  # set of Workload objects directly referenced from the problems
    limiting_sets: Set[
        LimitingSet
    ] = set()  # set of Limiting_set objects indirectly referenced from the problems
    #  (via instance classes)
    instance_classes: Set[
        InstanceClass
    ] = set()  # set of Instance_class objects directly referenced from the problems
    performances: Set[
        PerformanceSet
    ] = set()  # set of Performance objects directly referenced from the problem

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

    _open = _get_open_function_from_extension(input_yaml_filename)

    output = []
    with _open(input_yaml_filename, mode="rt", encoding="utf8") as istream:
        for line in istream:
            if line.startswith("Problems_from_file"):
                filename = line.split(":")[1].strip()
                line = read_file_relative_to(
                    filename=filename, relative_to=input_yaml_filename
                )
            output.append(line)
    return "".join(output)


def read_file_relative_to(filename: str, relative_to: str, kind: str = "yaml") -> str:
    """Reads one file by its name, considered relative to other filename.

    Args:
        filename: the name of the file to read
        relative_to: the name of the file to which the first one is considered relative
        kind: expected extension of the filename

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
    _open = _get_open_function_from_extension(filename, kind=kind)
    return _open(path_to_filename, mode="rt", encoding="utf8").read()


def read_from_relative_csv(filename: str, relative_to: str) -> Tuple[float, ...]:
    """Reads and parses the content of one file, given its name considered relative to other
    filename.

    The file is first read by :func:`read_file_relative_to()` and the contents are assumed
    to be a sequence of floating numbers, one per line.

    Args:
        filename: the name of the file to read
        relative_to: the name of the file to which the first one is considered relative

    Returns:
        The sequence of read floating numbers, as a tuple.

    Raises:
        FileNotFoundError: If the file is not found.
    """
    content = read_file_relative_to(filename, relative_to, kind="csv")
    return tuple(float(line) for line in content.split("\n") if line)


def solutions_to_yaml(solutions: Sequence[Union[SolutionI, SolutionII]]) -> str:
    """Converts a list of solutions to a YAML string.

    Args:
        solutions: list of solutions to convert, each one can be a
            :class:`SolutionI` or a :class:`SolutionII`.
    Returns:
        A string with a YAML representation of the solution and the
        associated problem. The YAML uses anchors and references
        to tie up the different parts.
    """

    def solution_i_to_yaml(sol: SolutionI) -> List[str]:
        """Converts a SolutionI to a yaml string"""
        lines: List[str] = []
        lines.extend(
            (
                "- &{}".format(_anchor_from_id(sol)),
                "  id: {}".format(sol.id),
                "  problem: *{}".format(_anchor_from_id(sol.problem)),
            )
        )
        lines.append("  solving_stats:")
        lines.extend(solving_stats_to_yaml(sol.solving_stats, level=2))

        lines.append("  reserved_allocation:")
        lines.extend(reserved_allocation_to_yaml(sol.reserved_allocation, level=2))

        lines.append("  allocation:")
        lines.extend(allocation_to_yaml(sol.allocation, level=2))

        return lines

    def solution_ii_to_yaml(sol: SolutionII) -> List[str]:
        """Converts a SolutionII to a yaml string"""
        lines: List[str] = []
        lines.extend(
            (
                "- &{}".format(_anchor_from_id(sol)),
                "  id: {}".format(sol.id),
                "  problem: *{}".format(_anchor_from_id(sol.problem)),
                "  previous_phase: *{}".format(_anchor_from_id(sol.previous_phase)),
            )
        )

        lines.append("  global_solving_stats:")
        lines.extend(global_solving_stats_to_yaml(sol.global_solving_stats, level=2))

        lines.append("  solving_stats:")
        for i, stats in enumerate(sol.solving_stats):
            lines.append(
                "    - # {} -> {}".format(i, sol.allocation.workload_tuples[i])
            )
            lines.extend(solving_stats_to_yaml(stats, level=3))

        lines.append("  allocation:")
        lines.extend(allocation_to_yaml(sol.allocation, level=2))
        return lines

    def solving_stats_to_yaml(stats: SolvingStats, level: int) -> List[str]:
        """Converts a SolvingStats to a yaml string"""
        lines: List[str] = []
        tab = "  " * level
        lines.extend(
            (
                "{}creation_time: {}".format(tab, stats.creation_time),
                "{}solving_time: {}".format(tab, stats.solving_time),
                "{}optimal_cost: {}".format(tab, _yamlize(stats.optimal_cost)),
                "{}algorithm:".format(tab),
                "  {}malloovia:".format(tab),
            )
        )
        lines.extend(_namedtuple_to_yaml(stats.algorithm, level=level + 2))
        return lines

    def global_solving_stats_to_yaml(
        stats: GlobalSolvingStats, level: int
    ) -> List[str]:
        """Converts a GlobalSolvingStats to a yaml string"""
        lines: List[str] = []
        tab = "  " * level
        lines.extend(
            (
                "{}creation_time: {}".format(tab, stats.creation_time),
                "{}solving_time: {}".format(tab, stats.solving_time),
                "{}optimal_cost: {}".format(tab, stats.optimal_cost),
                "{}status: {}".format(tab, stats.status.name),
            )
        )
        return lines

    def reserved_allocation_to_yaml(rsv: ReservedAllocation, level: int) -> List[str]:
        """Converts a ReservedAllocation to a yaml string"""
        lines: List[str] = []
        tab = "  " * level
        if rsv is None:
            instance_classes: List[InstanceClass] = []
            vms_number: List[float] = []
        else:
            instance_classes = list(rsv.instance_classes)
            vms_number = list(rsv.vms_number)
        lines.extend(
            (
                "{}instance_classes: [{}]".format(
                    tab, list_of_references_to_yaml(instance_classes)
                ),
                "{}vms_number: [{}]".format(tab, ", ".join(str(v) for v in vms_number)),
            )
        )
        return lines

    def list_of_references_to_yaml(lst: Sequence[Any]) -> str:
        """Generates a comma separated list of yaml references using the id"""
        return ", ".join("*{}".format(_anchor_from_id(element)) for element in lst)

    def list_to_yaml(lst: Iterable[Any]) -> str:
        """Generates a comma separated list of python objects"""
        return ", ".join(str(element) for element in lst)

    def allocation_to_yaml(alloc: AllocationInfo, level: int) -> List[str]:
        """Converts an AllocationInfo to a yaml string"""
        lines: List[str] = []
        tab = "  " * level
        if alloc is None:
            instance_classes: List[InstanceClass] = []
            workload_tuples: List[Tuple[float, ...]] = []
            apps: List[App] = []
            repeats: List[int] = []
            values: Tuple[Tuple[Tuple[float, ...], ...], ...] = tuple()
        else:
            instance_classes = list(alloc.instance_classes)
            workload_tuples = list(alloc.workload_tuples)
            apps = list(alloc.apps)
            repeats = list(alloc.repeats)
            values = tuple(alloc.values)
        lines.extend(
            (
                "{}instance_classes: [{}]".format(
                    tab, list_of_references_to_yaml(instance_classes)
                ),
                "{}apps: [{}]".format(tab, list_of_references_to_yaml(apps)),
                "{}workload_tuples: [{}]".format(
                    tab, list_to_yaml(list(wl) for wl in workload_tuples)
                ),
                "{}repeats: [{}]".format(tab, list_to_yaml(repeats)),
            )
        )
        if values:
            lines.append("{}vms_number:".format(tab))
            for i, t_alloc in enumerate(values):
                lines.append("  {}- # {} -> {}".format(tab, i, workload_tuples[i]))
                for app_alloc in t_alloc:
                    lines.append("    {}- {}".format(tab, list(app_alloc)))
        else:
            lines.append("{}vms_number: []".format(tab))
        return lines

    # First collect all problems referenced in the solutions
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
                "Solution({}) is of unknown type {}".format(solution.id, type(solution))
            )
    return "\n".join(lines)


def _namedtuple_to_yaml(data, level=2):
    """Converts to yaml any namedtuple, via dict.

    Args:
        data: the namedtuple to convert
        level: the indentation level

    Returns:
        array of lines to add to yaml array
    """
    return _dict_to_yaml(data._asdict(), level)


def _dict_to_yaml(data, level):
    """Converts to yaml any dictionary, by iterating through its keys and values.

    Args:
        data: the dict to convert
        level: the indentation level

    Returns:
        array of lines to add to yaml array
    """
    lines = []
    for key, value in data.items():
        value = _yamlize(value)
        lines.append("{}{}: {}".format("  " * level, key, value))
    return lines


def _yamlize(value: Any) -> Any:
    """Converts a python value to a valid YAML representation.

    Args:
        value: the python value to convert

    Returns:
        Either a string containing ``"null"``, ``"true"`` or ``"false"``
        for the special cases ``None``, ``True`` and ``False``, resp., or
        ``value.name`` if present (for ``Enum``\\ s), or
        the same value received as input for other cases."""

    if value is None:
        return "null"

    if value is True:
        return "true"

    if value is False:
        return "false"

    if hasattr(value, "name"):  # For Enums
        return value.name  # pylint:disable=no-member

    return value


def get_schema() -> Dict[str, Any]:
    """Returns Malloovia's json schema which can be used to validate the
    problem and solution files"""

    path_to_schema = os.path.join(os.path.dirname(__file__), "malloovia.schema.yaml")
    with open(path_to_schema) as schema_file:
        schema = yaml.safe_load(schema_file)
    return schema


def allocation_info_as_dicts(
    alloc: AllocationInfo,
    use_ids=True,
    include_timeslot=True,
    include_workloads=True,
    include_repeats=True,
) -> Iterable[Mapping[Any, Any]]:
    """Converts the :class:`AllocationInfo` structure to a sequence of dicts, which
    are more convenient for analysis with pandas. Each element of the returned
    sequence is a python dictionary whose keys and values are:

        * "instance_class" -> either the id or the reference to an instance class
        * "app" -> either the id or the reference to an app
        * "timeslot" -> the integer which represents the timeslot for this particular allocation
        * "workload" -> a tuple with the workload to be fulfilled by this particular allocation
        * "repeats" -> the number of times this workload appears in phaseI (always 1 for phase II)
        * AllocationInfo.units -> value for this particular allocation. If the units is "vms",
          the value represents the number of VMs of the kind "instance_class" to be activated
          during timeslot "timeslot" (in phase II), or when the workload is "workload" (in
          phase I), for the application "app".

    Some of these fields are useful only for Phase I, while others are for Phase II. Some
    boolean arguments allow the selection of these specific fields.

    Args:
        alloc: The :class:`AllocationInfo` to convert
        use_ids: True to use the ids of instance classes and apps, instead of the objects
           which store those entities. False to use references to instance classes and apps
           instead of the ids. The ids version produces a more compact representation when
           used with pandas.
        include_timeslot: False if you don't want the "timeslot" field (it conveys no meaning
            for Phase I allocations)
        include_workloads: False if you don't want the "workload" field
        include_repeats: False if you don't want the "repeats" field (it is always 1 for
            Phase II allocations)

    Returns:
        A generator for sequence of dictionaries with the required fields. You can iterate
        over the generator, or pass it directly to pandas DataFrame constructor.

    Example:

        >>> import pandas as pd
        >>> df = (pd.DataFrame(
                allocation_info_as_dicts(
                    alloc = phase_i_solution.allocation,
                    use_ids=True,
                    include_repeats=True,
                    include_workloads=True,
                    include_timeslot=False))
                .set_index(["repeats", "workload", "app", "instance_class"])
                .unstack()
            )
        >>> df
                                      vms
        instance_class            m3large   m3large_r
        repeats workload    app
        1       (30, 1194)  app0     0.0       3.0
                            app1     0.0       3.0
                (32, 1200)  app0     1.0       3.0
                            app1     0.0       3.0
        2       (30, 1003)  app0     0.0       3.0
                            app1     0.0       3.0
        >>> df2 = (pd.DataFrame(
                allocation_info_as_dicts(
                    alloc = phase_ii_solution.allocation,
                    use_ids=True,
                    include_repeats=False,
                    include_workloads=True,
                    include_timeslot=True))
                .set_index(["timeslot", "workload", "app", "instance_class"])
                .unstack()
            )
        >>> df
                                     vms
        instance_class           m3large   m3large_r
        timeslot workload   app
        0        (30, 1003) app0     0.0       3.0
                            app1     0.0       3.0
        1        (32, 1200) app0     1.0       3.0
                            app1     0.0       3.0
        2        (30, 1194) app0     0.0       3.0
                            app1     0.0       3.0
        3        (30, 1003) app0     0.0       3.0
                            app1     0.0       3.0
    """

    def _repr(element):
        if use_ids:
            return element.id

        return element

    for slot, t_alloc in enumerate(alloc.values):
        for app, a_alloc in enumerate(t_alloc):
            for i, ic_alloc in enumerate(a_alloc):
                result = {}
                result["instance_class"] = _repr(alloc.instance_classes[i])
                result["app"] = _repr(alloc.apps[app])
                result[alloc.units] = ic_alloc
                if include_workloads:
                    result["workload"] = alloc.workload_tuples[slot]
                if include_timeslot:
                    result["timeslot"] = slot
                if include_repeats:
                    result["repeats"] = alloc.repeats[slot]
                yield result


def _get_open_function_from_extension(filename, kind="yaml"):
    """Returns the function open is the extension is ``kind`` or
    'gzip.open' if it is ``kind``.gz'; otherwise, raises ValueError
    """
    if filename.endswith(".{}.gz".format(kind)):
        return gzip.open
    elif filename.endswith(".{}".format(kind)):
        return open
    else:
        raise ValueError("Invalid filename. Should be .{} or .{}.gz".format(kind, kind))


__all__ = [
    "read_problems_from_yaml",
    "read_problems_from_github",
    "problems_to_yaml",
    "solutions_to_yaml",
    "get_schema",
    "allocation_info_as_dicts",
]
