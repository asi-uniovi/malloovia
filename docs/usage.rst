.. _usage:

Usage
=========

This section shows how to specify an example problem, how to solve it and how to inspect the solution, using Malloovia's :ref:`API <api>`.
The same can be done without writing any python code,
by using the :ref:`YAML specification <yaml>` of the problem and :ref:`Malloovia's command-line interface <cli>`.

It is assumed that ``from malloovia import *`` was done before the code examples.
Next to each snippet of python code, the YAML equivalent form is shown (collapsed by default).


System specification
----------------------------

The specification of the system is the description of the cloud infrastructure in which the applications will run
and the performance of these applications on the given infrastructure.

Infrastructure
++++++++++++++

The data about the cloud infrastructure is stored in different entities:

* :class:`.LimitingSet` defines some constraints imposed by the cloud provider about the maximum number of virtual machines or cores which can be running in a region or availability zone.
* :class:`.InstanceClass` represents one particular type of virtual machine to be deployed in one particular cloud provider and region/availability
  zone.
  It holds information about the price (per hour in this example), limits and whether it is a reserved (prepaid for a whole reservation period) or on-demand (pay-per-use).

Example:

.. testcode::

    region1 = LimitingSet("r1", name="us.east", max_vms=20)
    zone1 =  LimitingSet("r1_z1", name="us.east_a", max_vms=20)
    m3large_z1 = InstanceClass(
        "m3large_r1_z1", name="reserved m3.large in us.east_a",
        limiting_sets=(zone1,), is_reserved=True,
        price=7, time_unit="h", max_vms=20)
    m4xlarge_r1 = InstanceClass(
        "m4xlarge_r1", name="ondemand m4.xlarge in us.east",
        limiting_sets=(region1,), is_reserved=False,
        price=10, time_unit="h", max_vms=10)


.. container:: toggle

    .. container:: header

        **Show/hide YAML version**

    .. code-block:: yaml

        Limiting_sets:
          - &r1
            id: r1
            name: us.east
            max_vms: 20
          - &r1_z1
            id: r1_z1
            name: us.east_a
            max_vms: 20

        Instance_classes:
          - &m3large_z1
            id: m3large_z1
            name: reserved m3.large in us.east_a
            limiting_sets: [*r1_z1]
            is_reserved: true
            price: 7
            time_unit: h
            max_vms: 20
          - &m4xlarge_r1
            id: m4xlarge_r1
            name: ondemand m4.xlarge in us.east
            limiting_sets: [*r1]
            is_reserved: false
            price: 10
            time_unit: h
            max_vms: 10

Note that in Python the name of the variables which store the data are not required to be the same than the internal ``id`` given to the corresponding objects.
For example, the first region has the ``id`` "r1", while the python variable is called ``region1``.
However, it is the name of the python variable what is used later to relate a particular ``InstanceClass`` with a previously created ``LimitingSet``.
Also note that, since the ``limiting_sets`` field must contain a tuple, the weird syntax ``(zone1,)`` has to be used when that tuple has a single element.
Without the comma inside the parenthesis, python would not parse correctly the value as a tuple.

In the YAML format, however, each object has an "anchor", prefixed by ``&`` (e.g.: ``&r1``) which is used later to refer to that particular object when it is used as part of other objects (``*r1`` inside the instance class).
In YAML, the names of the python variables are irrelevant, and the ``id``\ s are used instead to create those anchors and to refer to them.

Performances
++++++++++++

Each instance class gives a different performance for each possible application.
These numbers are assumed to be known (found by benchmarking or monitoring), and given by the analyst.
To specify this information Malloovia provides two additional classes:

* :class:`.App` declares one application, consisting simply in a unique ``id`` and a user-friendly ``name``.
* :class:`.PerformanceValues` stores the performance of each pair (app, instance_class), from a python dictionary whose keys are the instance classes, containing nested dictionaries whose keys are the apps.
* :class:`.PerformanceSet` gives a unique ``id`` to a particular case of :class:`.PerformanceValues`, and makes explicit the time unit used (hours in this example).

Example:

.. testcode::

    app0 = App("a0", "Web server")
    app1 = App("a1", "Database")
    performances = PerformanceSet(
        id="example_perfs",
        time_unit="h",
        values=PerformanceValues({
            m3large_z1: {app0: 12, app1: 500},
            m4xlarge_r1: {app0: 44, app1: 1800}
            })
    )


.. container:: toggle

    .. container:: header

        **Show/hide YAML version**

    .. code-block:: yaml

        Apps:
        - &a0
          id: a0
          name: Web server
        - &a1
          id: a1
          name: Database

        Performances:
        - &example_perfs
          id: example_perfs
          time_unit: h
          values:
          - instance_class: *m3large_z1
            app: *a0
            value: 12
          - instance_class: *m3large_z1
            app: *a1
            value: 500
          - instance_class: *m4xlarge_r1
            app: *a0
            value: 44
          - instance_class: *m4xlarge_r1
            app: *a1
            value: 1800


Workload specification
----------------------

Malloovia deals with different applications, each one characterized by its own workload.
The solving algorithm requires a prediction of the workload for each application.
For Phase I, a long-term workload prediction (LTWP) is required, which contains the expected workload for each timeslot for the whole reservation period.
For Phase II, a short-term workload prediction (STWP) is required, which contains the expected workload for the next timeslot only.
However, malloovia can also perform a simulation of phase II over an arbitrary number of timeslots, if a list of STWP is given.

In order to store either the LTWP, or a single-timeslot STWP, or a list of STWP for any number of timeslots (to simulate Phase II), the class :class:`.Workload` is provided.

* A :class:`.Workload` object contains a sequence of numbers (which can be a single one), which is either the LTWP or a series of STWP, and the time unit used (i.e: what is the length of the timeslot, which is one hour in this example).
  It also contains the reference to the application related to that workload, a unique ``id`` and a short description.

Example:

.. testcode::

    # Long term workload prediction of each app, for Phase I
    # Note that all workloads for all apps must use the same time_unit
    ltwp_app0 = Workload(
        "ltwp0", description="rph to the web server", app=app0,
        time_unit="h",
        values=(201, 203, 180, 220, 190, 211, 199, 204, 500, 200)
    )
    ltwp_app1 = Workload(
        "ltwp1", description="rph to the database", app=app1,
        time_unit="h",
        values=(2010, 2035, 1807, 2202, 1910, 2110, 1985, 2033, 5050, 1992)
    )

.. container:: toggle

    .. container:: header

        **Show/hide YAML version**

    .. code-block:: yaml

       Workloads:
         - &ltwp0
           id: ltwp0
           description: rph to the web server
           time_unit: h
           values: [201, 203, 180, 220, 190, 211, 199, 204, 500, 200]
           app: *a0
         - &ltwp1
           id: ltwp1
           description: rph to the database
           time_unit: h
           values: [2010, 2035, 1807, 2202, 1910, 2110, 1985, 2033, 5050, 1992]
           app: *a1

Building the problem
-------------------------

Once all infrastructure, performances and workload prediction are defined, they are grouped in a :class:`.Problem`.

* :class:`.Problem` is the object which groups all the above, i.e:
  the list of instance classes, the performance values, and the workload predictions, which are used as the input of Malloovia's algorithm.

Example:

.. testcode::

    problem = Problem(
        id="example1",
        name="Example problem",
        workloads=(ltwp_app0, ltwp_app1),
        instance_classes=(m3large_z1, m4xlarge_r1),
        performances=performances
    )

.. container:: toggle

    .. container:: header

        **Show/hide YAML version**

    .. code-block:: yaml

       Problems:
         - &example1
           id: example1
           name: Example problem
           workloads: [*ltwp0, *ltwp1]
           instance_classes: [*m3large_z1, *m4xlarge_r1]
           performances: *example_perfs
           description: Nondescript

This completes the problem definition.
If all above code snippets are pasted in a single file, the result will be a valid Python program (or a valid YAML file in the case of YAML snippets), ready to be solved by Malloovia.

Solving
-------

Phase I
+++++++

To solve phase I, the problem is expected to contain in the ``workloads`` field the LTWP.
This usually means that the length of the ``values`` field in each workload is 8760, i.e. the number of hours in a year.

However, in order to keep the problem simple, we used a workload containing only 10 values.
This is also accepted by Malloovia, and it is interpreted as the reservation period consisting on 10 timeslots.
Malloovia does not make assumptions about the real-time length of one timeslot, but the length of the workload informs it about the number of timeslots in the reservation period.

To solve the problem:

.. testcode::

    phase_i_solution = PhaseI(problem).solve()

The time required to complete the solution depends on the length of the workloads, the number of different instance_classes, and the proximity of the optimal solution to the region/zone limits.
It can be as fast as a few seconds, or as long as several hours (perhaps days).

You can influence the time in which the solution is found by passing a customized solver as parameter.
For example::

    phase_i_solution = PhaseI(problem).solve(solver=COIN(maxSeconds=30, fracGap=0.01))

You need to use ``from pulp import COIN`` for this to work, and also have COIN-OR cbc binary installed in your system (see :ref:`installation <install>` for details).
In this particular example we limit the solving time to 30 seconds,
and set a "frac-gap" of 0.01, which means that the solver stops when the solution found is near (in a fraction of 0.01) to the best lower bound known.
You can also pass the option ``threads=N`` to ``COIN()``, to use ``N`` cores in your machine (in this case the ``maxSeconds`` time is the divided by the number of threads).

It may happen that no solution can be found,
either because the problem is infeasible
(the workload prediction cannot be fulfilled without violating the system limits),
or because the ``maxSeconds`` time was reached and no good solution was still found.
The solution object contains information to determine if this was the case.
See :ref:`Inspecting the solution <inspect_sol>` for details.

Phase II
++++++++

Once phase I is solved, the optimal number of reserved instances found by the solver is used as input for phase II.
Usually phase II is a new problem, which uses the same infrastructure and performances used in phase I, but a different workload prediction.
The workload prediction for phase II can use different time units than the ones used in phase I. It is possible for example to have a LTWP per hour, and a STWP per minute.

It is possible to instantiate a :class:`.PhaseII` and then use it to solve a single timeslot, for example,
assume that we predict that the next timeslot (hour) will have a workload of 315 rph for app0, and 1950 rph for app1.
The following snippet shows how to find the optimal allocation for such a timeslot:


.. testcode::

    phase_ii = PhaseII(problem, phase_i_solution)
    timeslot_solution = phase_ii.solve_timeslot(
        workloads=(Workload("stwp0", app=app0, description=None, time_unit="h", values=(315,)),
                   Workload("stwp1", app=app1, description=None, time_unit="h", values=(1950,))
                   )
        )


When used this way, the values stored in ``problem.workloads`` are not used in this phase, and instead the workloads passed to ``solve_timeslot()`` are used.
Note that in this case each ``values`` field is a tuple with a single element (if more elements were present, only the first one would be used).

For simulation purposes, :class:`.PhaseII` provides also a ``.solve_period()`` method, which can be called in two different ways:

*Without arguments*

    In this case it will use the values stored in ``problem.workloads`` as a sequence of several STWP, and will iterate over them, solving a timeslot for each element.
    If the ``problem`` passed to the constructor is the same than the one used in Phase I, this would mean that the LTWP was perfect, and the STWP is identical to the LTWP.
    This is of course an unreasonable scenario, but can be used to test that Phase II provides the same optimal cost than Phase I for this case.

    Example:

    .. testcode::

        phase_ii = PhaseII(problem, phase_i_solution)
        period_solution = phase_ii.solve_period()

*With predictor argument*

    A predictor is a generator which yields a tuple of workloads each time it is called, and that tuple is used to solve a single timeslot.
    ``PhaseII.solve_period()`` will iterate over that generator until it is exhausted.
    In this case the values stored in ``problem.workloads`` are not used, being replaced by the values provided by the predictor.

    Malloovia provides a dumb predictor, useful for simulation purposes, called :class:`.OmniscientSTWPredictor` which receives as parameter of its constructor a sequence of workloads,
    like the one stored in ``problem`` for phase I, and returns one tuple at a time when iterated.
    This can be used to provide different STWP to the same problem. For example:

    .. testcode::

        phase_ii = PhaseII(problem, phase_i_solution)
        predictor = OmniscientSTWPredictor((
            Workload(
                "stwp0", description="rph to the web server", app=app0,
                values=(221, 190, 210, 240, 180, 150, 505, 200, 250, 180),
                time_unit="h"
            ),
            Workload(
                "stwp1", description="rph to the database", app=app1,
                values=(2215, 1904, 2100, 2410, 1802, 1504, 5070, 1990, 2510, 1805),
                time_unit="h"
            )))
        period_solution = phase_ii.solve_period(predictor)

.. _inspect_sol:


Inspecting the solution
-----------------------

.. warning::

    TO-DO
