# coding: utf-8
"""This module implements the base classes which define a
problem to be solved by Malloovia.

All these classes are immutable (most of them are :class:`namedtuple`\\ s).
Usually they are initialized via the functions provided in :mod:`util` module.
For example::

  problems = malloovia.util.read_problems_from_yaml("problems.yaml")

This will return a dictionary in which the keys are problem_ids and the
values are :class:`Problem` instances, whose attributes provide access to all
other entities.
"""

from collections import namedtuple
from typing import Mapping, Tuple, NamedTuple, Optional, Set, Dict
import copy
import sys


###############################################################################
# All main malloovia entities are defined as namedtuples, via typing.NamedTuple


def remove_namedtuple_defaultdoc(cls):
    """This decorator removes the __doc__ which namedtuples get
    automatically for their __new__() constructor and their fields
    """
    for f in cls._fields:
        getattr(cls, f).__doc__ = None
    cls.__new__.__doc__ = "{}({})".format(cls.__name__, ",".join(cls._fields))
    if "id" in cls._fields:
        cls.__repr__ = lambda self: "{}('{}')".format(cls.__name__, self.id)
    return cls


@remove_namedtuple_defaultdoc
class Problem(NamedTuple):
    """Problem description.
    """

    id: str
    """:obj:`str`: arbitary id for the problem object."""

    name: str
    """:obj:`str`: name for the problem."""

    workloads: Tuple["Workload", ...]
    """:obj:`Tuple` [:class:`.Workload`, ...]: Tuple of workloads, one per application."""

    instance_classes: Tuple["InstanceClass", ...]
    """Tuple[:class:`.InstanceClass`, ...]: Tuple of Instance Classes, 
            describing the cloud infrastructure which has to serve the workload."""

    performances: "PerformanceSet"
    """:class:`.PerformanceSet`: Object describing the performance of each instance class
            for each kind of application."""

    description: str = "Nondescript"
    """str: optional description for the problem."""


@remove_namedtuple_defaultdoc
class Workload(NamedTuple):
    """Workload description"""

    id: str
    "str: arbitrary id for the workload object."

    description: str
    "str: description of the workload."

    values: Tuple[float, ...]
    """Tuple[float, ...]: the value of the predicted workload for several timeslots.
            It can store also a single value if it is the short-term workload
            prediction, but even in this case it must be a tuple (with
            a single element)."""

    app: "App"
    """:class:`.App`: The application which generates this workload."""

    time_unit: str
    """string: length of the timeslot used in values ("y", "h", "m", or "s")."""

    intra_slot_distribution: str = "uniform"
    """str: optional identifier of the statistical distribution of this workload
           inside the timeslot. Malloovia does not use this attribute, but
           it can be used by other tools, like simulators."""

    filename: Optional[str] = None
    """str: optional name of the file from which this workload was read,
            or None if the filename is unknown."""


@remove_namedtuple_defaultdoc
class InstanceClass(NamedTuple):
    "InstanceClass characterization"

    id: str
    """str: arbitrary id for the instance class object."""

    name: str
    """str: name of the instance class, usually built from the name of the VM type
        and the name of the limiting set in which it is deployed."""

    limiting_sets: Tuple["LimitingSet", ...]
    """Set[:class:`.LimitingSet`]: tuple of :class:`.LimitingSet` objects to which
        this instance class belongs. Usually this tuple has a single element,
        but in principle an instance class can be restricted by several
        limiting sets."""

    max_vms: int
    """int: maximum number of VMs which can be deployed from this instance class.
        The value 0 means "no limit"."""

    price: float
    """float: price per timeslot of this instance class."""

    time_unit: str
    """str: length of the timeslot used in price ("y", "h", "m", or "s")."""

    is_reserved: bool = False
    """bool: True if this instance class is reserved (defaults to False)."""

    cores: int = 1
    """int: number of cores this instance class has (defaults to 1)."""

    is_private: bool = False
    """bool: True if this instance class belongs to the private cloud in a 
    hybrid model (defaults to False)"""


@remove_namedtuple_defaultdoc
class LimitingSet(NamedTuple):
    """LimitingSet restrictions."""

    id: str
    "str: arbitrary id for limiting set object."

    name: str
    "str: name of the limiting set."

    max_vms: int = 0
    """int: maximum number of VMs which can be running inside this limiting set.
        Defaults to 0 which means "no limit"."""

    max_cores: int = 0
    """float: maximum number of cores which can be running inside this
        limiting set. Defaults to 0 which means "no limit"."""


@remove_namedtuple_defaultdoc
class App(NamedTuple):
    """App identifier.
   """

    id: str
    """str: arbitrary id for the App object"""

    name: str = "unnamed"
    """name of the app"""


@remove_namedtuple_defaultdoc
class PerformanceSet(NamedTuple):
    """Stores the performance of each pair (app, instance class)."""

    id: str
    "str: arbitrary id for the PerformanceSet object."

    values: "PerformanceValues"
    """:class:`.PerformanceValues`: storage of the performance values per app
        and instance class."""

    time_unit: str
    """str: length of the timeslot used in performance values ("y", "h", "m", or "s")."""


@remove_namedtuple_defaultdoc
class System(NamedTuple):
    """Stores the part of a problem which does not depend on the workload."""

    id: str
    "str: arbitary id for the system object."

    name: str
    "str: name for the problem."

    apps: Tuple[App, ...]
    """Tuple[:class:`.App`, ...]: Tuple of objects of type :class:`.App` describing
        the applications that are used in the system."""

    instance_classes: Tuple[InstanceClass, ...]
    """Tuple[:class:`.InstanceClass`, ...]: Tuple of objects of type
        :class:`.InstanceClass`, describing the cloud infrastructure which
        has to serve the workload."""

    performances: PerformanceSet
    """:class:`.PerformanceSet`: Object describing the performance of each
        instance class for each kind of application."""


def check_valid_problem(problem: Problem) -> Problem:
    """Performs some sanity checks on the problem's definition.

    Args:
        problem: the problem to check
    Returns:
        The same problem if all is correct
    Raises:
        ValueError: if some error is detected.
    """
    apps = tuple(w.app for w in problem.workloads)
    length = len(problem.workloads[0].values)
    if not all(len(w.values) == length for w in problem.workloads):
        raise ValueError("All workloads in the problem should have the same length")
    for iclass in problem.instance_classes:
        if iclass not in problem.performances.values.keys():
            raise ValueError("Performance data for {} is missing".format(iclass))
    for iclass, ic_data in problem.performances.values.items():
        for app in apps:
            if app not in ic_data.keys():
                raise ValueError(
                    "Performance data for {} in {} is missing".format(app, iclass)
                )
    # Everything is awesome
    return problem


def system_from_problem(problem: Problem) -> System:
    """Extracts the "system" part of a problem.

    Args:
        problem: Problem description
    Returns:
        A :class:`System` object containing a copy of the relevant parts of the problem.
    """
    return System(
        id=problem.id,
        name=problem.name,
        apps=tuple(w.app for w in problem.workloads),
        instance_classes=problem.instance_classes,
        performances=problem.performances,
    )


######################################################################################

# PerformanceValues is not a namedtuple, but a class which encapsulates a dict
# trying to being as immutable as possible (python doesn't have frozendicts)
#
# The class uses __slots__ to prevent the addition of more attributes, and
# an internal attribute __perfs whose name is mangled by python to make
# more difficult to access to it from outside the class.
class PerformanceValues(object):  # pylint: disable=R0903
    """Stores the performance of each app for each instance class.

    If ``p`` is an instance of this class, performance data can be accessed like
    this: ``p[ic, app]``, being ``ic`` and ``app`` instances of :class:`InstanceClass`
    and :class:`App`, respectively.

    Also ``p.get_by_id(ic_id, app_id)`` can be used, being ``ic_id`` and ``app_id`` strings
    (corresponding to ``ic.id`` and ``app.id`` fields of :class:`InstanceClass` and :class:`App`)

    :class:`PerformanceValues` implements the iterator interface, so you can loop over it,
    as for example ``for (i, a, v) in p:`` Each iteration yields a tuple
    ``(instance_class, app, value)``. The order in which the items are retrieved is
    deterministic, alphabetical by id.
    """

    __slots__ = ("__perfs", "__perfs_by_id", "__ics", "__apps")

    def __init__(self, data: Mapping[InstanceClass, Mapping[App, float]]) -> None:
        """Constructor:

        Args:
            data (dict): It is expected that the keys are instance classes, and the values
                are nested dictionaries with apps as keys and performances (float)
                as values.

                This dictionary is copied inside the class, so that later
                modifications to the passed dictionary do not affect the
                internal copy.
        """
        # Two copies of the information are stored. One is a copy of the
        # original dictionary, indexed by python objects.
        # The second is indexed by ic and app ids, which is more convenient
        # for repr(), to_yaml(), and get_by_id()
        self.__perfs = copy.deepcopy(data)
        self.__perfs_by_id: Dict[str, Dict[str, float]] = {}
        self.__ics: Set[InstanceClass] = set()
        self.__apps: Set[App] = set()
        for ins, app_perfs in data.items():
            self.__ics.add(ins)
            aux = {}
            for app, perf in app_perfs.items():
                self.__apps.add(app)
                aux[app.id] = perf
            self.__perfs_by_id[ins.id] = aux

    def __getitem__(self, ic_app: Tuple[InstanceClass, App]) -> float:
        """Get the performance of a pair (instance class, application).

        Args:
            ic_app: The pair (instance class, application) whose performance is looked up.
        Returns:
            The performance of that pair
        Raises:
            KeyError: when the instance class or application is not stored in this PerformanceSet.
        """
        ins = ic_app[0]
        app = ic_app[1]
        return self.__perfs[ins][app]

    def get_by_ids(self, ins_id: str, app_id: str) -> float:
        """Get the performance of a pair (instance class, app) by their ids.

        Args:
            ins_id: id of the instance class
            app_id: id of the app
        Returns:
            The performance value for that pair
        Raises:
            KeyError: when no instance class or app with those ids can be found.
        """

        return self.__perfs_by_id[ins_id][app_id]

    def __repr__(self):
        """Abridged representation of the class"""
        return "{} for ({} instance_classes x {} apps)".format(
            self.__class__.__name__, len(self.__ics), len(self.__apps)
        )

    def items(self):
        """Returns a view of the items in the private dictionary"""
        return self.__perfs.items()

    def keys(self):
        """Returns a view of the keys in the private dictionary"""
        return self.__perfs.keys()

    def __eq__(self, other):
        """Compares itself with another object"""
        if not isinstance(other, self.__class__):
            return False
        return self.items() == other.items()

    def __hash__(self):
        """Make it hashable so it can be stored in sets"""
        return id(self.__perfs)

    def __iter__(self):
        """Implements the iterable interface, by returning an iterator"""
        perfs = self.__perfs
        return (
            (ic, app, perfs[ic][app])
            for ic in sorted(perfs)
            for app in sorted(perfs[ic])
        )


class TimeUnit:
    """Provides a simple method to perform time units conversions.

    It stores as a class attribute a dictionary whose keys are strings representing the time units
    (eg: "h", "m", "s") and the values are the factor to convert one into another.
    The value for "s" is 1, for "m" it would be 60, etc.

    Inheritance can be used to extend the known time units. You have however to rewrite the
    whole dictionary plus the new units in the derived class."""

    conversion_factors = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 24 * 60 * 60,
        "y": 365 * 24 * 60 * 60,
    }

    def __init__(self, unit: str, amount: float = 1) -> None:
        """Creates a TimeUnit for the given unit.

        Args:
            unit: The string representing the time unit, e.g. "h" for hours
            amount: Amount of time units, defaults to 1.

        Raises:
            ValueError: if the string does not represent a known time unit
        """
        self.check_valid_unit(unit)
        self.unit = unit
        self.amount = amount

    def to(self, to_unit):
        """Convert this time unit into a different time unit.

        Args:
            to_unit: string representing the time unit to which convert, e.g. "s" for seconds

        Returns:
            The number of units of type "to_unit" in the time "self.unit". For example,
            TimeUnit("h").to("s") will return 3600.
        Raises:
            ValueError if "to_unit" is not a known time unit.
        """
        self.check_valid_unit(to_unit)
        return (
            self.amount
            * self.conversion_factors[self.unit]
            / self.conversion_factors[to_unit]
        )

    @classmethod
    def check_valid_unit(cls, unit):
        """Checks the validity of the time unit, by looking it up in the keys of
        the class attribute conversion_factors. Note that this allows for using inheritance
        to extend the list of known time units."""
        if unit not in cls.conversion_factors.keys():
            raise ValueError(
                "Unit {} is not valid. Use one of {}".format(
                    repr(unit), list(cls.conversion_factors.keys())
                )
            )


__all__ = [
    "Workload",
    "App",
    "InstanceClass",
    "LimitingSet",
    "PerformanceSet",
    "PerformanceValues",
    "Problem",
    "check_valid_problem",
    "System",
    "system_from_problem",
    "TimeUnit",
]
