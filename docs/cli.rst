.. _cli:
.. highlight:: bash

Command-line interface
======================

When installing Malloovia with ``pip``, a command line script is also installed in your path (inside the virtual environment if you used one to install Malloovia, as recommended).
You can try to invoke it from the terminal::

    $ malloovia
    Usage: malloovia [OPTIONS] COMMAND [ARGS]...

    Malloovia command line interface

    Options:
    --version  Show the version and exit.
    --help     Show this message and exit.

    Commands:
    solve     Solves phase I and optionally phase II of...
    validate  Validates yaml files

It can be used to validate :ref:`YAML files <yaml>` or to solve problems.

Validating YAML files
---------------------

The usage is simple::

    $ malloovia validate problem_file.yaml
    problem_file.yaml is correct

In case of error, a message is shown. Use ``--verbose`` to get more detail about the problem.
Use ``malloovia validate --help`` for more options.

Solving problems
----------------

It can be used to solve only phase I of a given problem, or phase I and then phase II.
In any case it is assumed that the definitions of the problems to be used for each phase are contained in the same yaml file.

For example, assume that there is a file ``problems.yaml`` which contains the definition of some infrastructure and performance data, as well as different workload predictions
(for example, one for the LTWP to be used in Phase I, and other for a simulation of the STWP to be used in Phase II),
and finally a section ``Problems:`` which defines two problems (with ids "problem1" and "problem2", respectively),
so that both are identical, except that the first problem uses the LTWP as workload while the second one uses the STWP.

The way to use malloovia cli for this example would be::

    $ malloovia solve problems.yaml --phase-i-id=problem1 --phase-ii-id=problem2
    Reading problems.yaml...(0.004s)
    Solving phase I...(0.020s)
    Solving Phase II |███████████████████████████████████| 100.0% - ETA: 0:00:00
    (0.101s)
    Writing solutions in problems-sol.yaml...(0.006s)

Malloovia loaded the yaml file and built the python description of ``problem1`` and ``problem2`` (it took 0.004s in this example).
It called ``malloovia.PhaseI(problem1).solve()`` (which took 0.20s) and stored the solution.
Then it called ``malloovia.PhaseII(problem2, phase_i_sol).solve_period()`` to iterate over the STWP stored in ``problem2``.
This example was very small and the STWP contained only 10 timeslots, so it finished in 0.101s,
but the usual case with 8760 timeslots if hours are used, or 525600 timeslots if minutes are used, takes time and thus a progress bar is displayed, which updates every 10 solved timeslots.
Finally, both solutions (the one for Phase I, and the other for the whole simulation period of Phase II) are written in a yaml file, which by default is named after the input file.

Option ``--phase-ii-id`` can be omitted, and then only phase I is performed. Option ``--phase-i-id`` cannot be omitted.

Use ``malloovia solve --help`` for more options. For example, it is possible to give values to ``frac-gap`` or ``max-seconds``
