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
from typing import (Mapping, Tuple)
import copy
import sys

def _namedtuple_with_defaults(name, mandatory, **defaults):
    """Creates a namedtuple which can have optional fields, with default
    values when not specified.

    Args:
        name: name of the new (namedtuple) class
        mandatory: sequence of names of the required fields (strings)
        **defaults: extra arguments whose name will be names of optional fields
            in the created class, and whose values will be the default values
            for those fields when not specified at the object creation.

    Returns:
        The new namedtuple class

    Example::

        Foo = _namedtuple_with_defaults("Foo",
                                        mandatory = ["id", "name", "value"],
                                        extra1="default1",
                                        extra2="default2")

    ``Foo`` will be a :class:`namedtuple` with five fields: "id", "name" and
    "value" which are mandatory (they should be passed as arguments to the
    namedtuple constructor), and "extra1" and "extra2" which are optional,
    and will have default values when not initialized. Eg::

        Foo(id=0, name="example", value=20)   # Will be valid
        Foo(id=0, name="example", value=20, extra2="some")  # Also valid
        Foo(name="example", extra1="foob", id=0, value=20)  # Also valid
        Foo(name="example", value=20) # Exception, required id not present
    """
    # Create the namedtuple with all fields, but putting the optional ones
    # after the mandatory ones
    _type = namedtuple(name, tuple(mandatory) + tuple(defaults.keys()))
    # Give the default values to the optional ones
    _type.__new__.__defaults__ = tuple(defaults.values())   # type: ignore
    # Modify the doc to inform about default values
    _type.__doc__ = "{}({}, {})".format(
        name,
        ", ".join(mandatory),
        ", ".join("{}={}".format(k, repr(v)) for k, v in defaults.items())
    )
    if "id" in  _type._fields:
        _type.__repr__ = lambda self: "%s('%s')" % (name, self.id)

    def _inspect(self):  # pragma: no cover
        print("{}:".format(self.__class__.__name__))
        for field, value in self._asdict().items():
            print("  {}: {!r}".format(field, value))

    _type._inspect = _inspect        # pylint: disable=protected-access

    # fix the module name, for pickle to work in these namedtuple_with_defaults
    # See original namedtuple code at
    # https://github.com/python/cpython/blob/3.5/Lib/collections/__init__.py#L437-L444
    try:
        _type.__module__ = sys._getframe(1).f_globals.get('__name__', '__main__')
    except (AttributeError, ValueError):
        pass
    return _type




###############################################################################
# All main malloovia entities are defined as namedtuples, via the
# _namedtuple_with_defaults factory defined above

Problem = _namedtuple_with_defaults(             # pylint: disable=invalid-name
    "Problem",
    ["id", "name", "workloads", "instance_classes",
     "performances"],
    description="Nondescript")
"""Problem description."""
Problem.id.__doc__ = "str: arbitary id for the problem object."
Problem.name.__doc__ = "str: name for the problem."
Problem.workloads.__doc__ = """\
    Tuple[:class:`Workload`]: Tuple of objects of type :class:`Workload`,
        one per application."""
Problem.instance_classes.__doc__ = """\
    Tuple[:class:`InstanceClass`]: Tuple of objects of type
        :class:`InstanceClass`, describing the cloud infrastructure which
        has to serve the workload."""
Problem.performances.__doc__ = """\
    :class:`PerformanceSet`: Object describing the performance of each
        instance class for each kind of application."""
Problem.description.__doc__ = "str: optional description for the problem."


Workload = _namedtuple_with_defaults(            # pylint: disable=invalid-name
    "Workload",
    ["id", "description", "values", "app", "time_unit"],
    intra_slot_distribution="uniform",
    filename=None)
"""Workload prediction for one application."""
Workload.id.__doc__ = "str: arbitrary id for the workload object."
Workload.description.__doc__ = "str: description of the workload."
Workload.values.__doc__ = """\
   Tuple[float]: the value of the predicted workload for several timeslots.
        It can store also a single value if it is the short-term workload
        prediction, but even in this case it must be a tuple (with
        a single element)."""
Workload.time_unit.__doc__ = """\
    string: length of the timeslot used in values ("y", "h", "m", or "s")."""
Workload.app.__doc__ = """\
    :class:`App`: The application which generates this workload."""
Workload.intra_slot_distribution.__doc__ = """\
    Enum: optional identifier of the statistical distribution of this workload
        inside the timeslot. Malloovia does not use this attribute, but
        it can be used by other tools, like simulators."""
Workload.filename.__doc__ = """\
    str: optional name of the file from which this workload was read,
        or None if the filename is unknown."""

InstanceClass = _namedtuple_with_defaults(       # pylint: disable=invalid-name
    "InstanceClass",
    ["id", "name", "limiting_sets", "max_vms", "price", "time_unit"],
    is_reserved=False,
    cores=1)
"""InstanceClass characterization."""
InstanceClass.id.__doc__ = """\
    str: arbitrary id for the instance class object."""
InstanceClass.name.__doc__ = """\
    str: name of the instance class, usually built from the name of the VM type
        and the name of the limiting set in which it is deployed."""
InstanceClass.limiting_sets.__doc__ = """\
    Set[:class:`LimitingSet`]: tuple of :class:`LimitingSet` objects to which
        this instance class belongs. Usually this tuple has a single element,
        but in principle an instance class can be restricted by several
        limiting sets."""
InstanceClass.max_vms.__doc__ = """\
    int: maximum number of VMs which can be deployed from this instance class.
        The value 0 means "no limit"."""
InstanceClass.price.__doc__ = """\
    float: price per timeslot of this instance class."""
InstanceClass.time_unit.__doc__ = """\
    string: length of the timeslot used in price ("y", "h", "m", or "s")."""
InstanceClass.is_reserved.__doc__ = """\
    bool: True if this instance class is reserved (defaults to False)."""
InstanceClass.cores.__doc__ = """\
    float: number of cores this instance class has (defaults to 1)."""


LimitingSet = _namedtuple_with_defaults(         # pylint: disable=invalid-name
    "LimitingSet",
    ["id", "name"],
    max_vms=0, max_cores=0)
"""LimitingSet restrictions."""
LimitingSet.id.__doc__ = "str: arbitrary id for limiting set object."
LimitingSet.name.__doc__ = "str: name of the limiting set."
LimitingSet.max_vms.__doc__ = """\
    int: maximum number of VMs which can be running inside this limiting set.
        Defaults to 0 which means "no limit"."""
LimitingSet.max_cores.__doc__ = """\
    float: maximum number of cores which can be running inside this
        limiting set. Defaults to 0 which means "no limit"."""

App = _namedtuple_with_defaults("App", ["id", "name"])  # pylint: disable=invalid-name
"""App identifier."""
App.id.__doc__ = "str: arbitrary id for the App object."
App.name.__doc__ = "str: name of the app."


PerformanceSet = _namedtuple_with_defaults(      # pylint: disable=invalid-name
    "PerformanceSet",
    ["id", "values", "time_unit"]
)
"""Stores the performance of each pair (app, instance class)."""
PerformanceSet.id.__doc__ = "str: arbitrary id for the PerformanceSet object."
PerformanceSet.values.__doc__ = """\
    :class:`PerformanceValues`: storage of the performance values per app
        and instance class."""
PerformanceSet.time_unit.__doc__ = """\
    string: length of the timeslot used in performance values ("y", "h", "m", or "s")."""


System = _namedtuple_with_defaults(             # pylint: disable=invalid-name
    "System",
    ["id", "name", "apps", "instance_classes", "performances"]
)
"""Stores the part of a problem which does not depend on the workload."""
System.id.__doc__ = "str: arbitary id for the system object."
System.name.__doc__ = "str: name for the problem."
System.apps.__doc__ = """\
    Tuple[:class:`App`]: Tuple of objects of type :class:`App` describing
        the applications that are used in the system."""
System.instance_classes.__doc__ = """\
    Tuple[:class:`InstanceClass`]: Tuple of objects of type
        :class:`InstanceClass`, describing the cloud infrastructure which
        has to serve the workload."""
System.performances.__doc__ = """\
    :class:`PerformanceSet`: Object describing the performance of each
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
        raise ValueError(
            "All workloads in the problem should have the same length")
    for iclass in problem.instance_classes:
        if iclass not in problem.performances.values.keys():
            raise ValueError(
                "Performance data for {} is missing".format(iclass))
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
        performances=problem.performances
    )

######################################################################################

# PerformanceValues is not a namedtuple, but a class which encapsulates a dict
# trying to being as immutable as possible (python doesn't have frozendicts)
#
# The class uses __slots__ to prevent the addition of more attributes, and
# an internal attribute __perfs whose name is mangled by python to make
# more difficult to access to it from outside the class.
class PerformanceValues(object):                 # pylint: disable=R0903
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
        self.__perfs_by_id = {}
        self.__ics = set()
        self.__apps = set()
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
            self.__class__.__name__,
            len(self.__ics),
            len(self.__apps)
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
        return ((ic, app, perfs[ic][app])
                for ic in sorted(perfs)
                for app in sorted(perfs[ic]))

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
        "h": 60*60,
        "d": 24*60*60,
        "y": 365*24*60*60
    }

    def __init__(self, unit:str, amount: float=1) -> None:
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
        return self.amount * self.conversion_factors[self.unit]/self.conversion_factors[to_unit]

    @classmethod
    def check_valid_unit(cls, unit):
        """Checks the validity of the time unit, by looking it up in the keys of
        the class attribute conversion_factors. Note that this allows for using inheritance
        to extend the list of known time units."""
        if unit not in cls.conversion_factors.keys():
            raise ValueError("Unit {} is not valid. Use one of {}".format(
                repr(unit), list(cls.conversion_factors.keys())))


__all__ = [
    'Workload', 'App', 'InstanceClass', 'LimitingSet',
    'PerformanceSet', 'PerformanceValues',
    'Problem', 'check_valid_problem',
    'System', 'system_from_problem',
    'TimeUnit'
]
