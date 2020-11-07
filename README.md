# Malloovia

[<img src="https://img.shields.io/badge/python->=3.6-blue.svg?style=flat-square">](https://www.python.org/downloads/) [<img src="https://img.shields.io/pypi/v/malloovia.svg">](https://pypi.python.org/pypi/malloovia) [<img src="http://readthedocs.org/projects/malloovia/badge/?version=latest" alt="Documentation Status">](http://malloovia.readthedocs.io/en/latest/?badge=latest)  [<img src="https://travis-ci.org/asi-uniovi/malloovia.svg?branch=master" alt=" Build status">](https://travis-ci.org/asi-uniovi/malloovia)


Use linear programming to allocate applications to cloud infrastructure.


* Free software: MIT license
* Documentation: https://malloovia.readthedocs.io.


## Introduction

Malloovia is a Python package to solve virtual machine (VM) allocation problems in Infrastructure as a Service (IaaS) clouds from the point of view of the cloud customer. It was first presented in the paper ["Cost Minimization of Virtual Machine Allocation in Public Clouds Considering Multiple Applications"](http://www.atc.uniovi.es/personal/joaquin-entrialgo/pdfs/Entrialgo2017-gecon.pdf) presented at [GECON 2017](http://2017.gecon-conference.org/).

The problem to solve is: given a cloud infrastructure composed of different virtual machine types, each one with its own hardware characteristics, and prices, some of them with different pricing schemas, such as discounts for reservation over long periods, and given a set of applications to run on that infrastructure, each one with a different performance on each different VM type, and with a different workload over time, find the number of VMs of each type to activate at each timeslot for each application, so that the expected workload is fulfilled for all applications, the cloud provider limits are not exceeded and the total cost is minimized.

It works in two phases: first, it computes the number of reserved VMs using a Long Term Workload Prediction (LTWP) and then, it computes the number of on-demand for each time slot using a Short Term Workload Prediction (STWP).

Malloovia can be directly used in Python or by a [CLI interface](https://malloovia.readthedocs.io/en/latest/cli.html#cli). The problems and the solutions can be saved using a [YAML format](https://malloovia.readthedocs.io/en/latest/yaml.html).

This is an example that assumes that the problem definition is in `problems.yaml`, with `problem1` describing the LTWP and `problem2` describing the STWP:

```
$ malloovia solve problems.yaml --phase-i-id=problem1 --phase-ii-id=problem2
Reading problems.yaml...(0.004s)
Solving phase I...(0.020s)
Solving Phase II |███████████████████████████████████| 100.0% - ETA: 0:00:00
(0.101s)
Writing solutions in problems-sol.yaml...(0.006s)
```

This is an example in Python (explained in more detail in the [Usage section of the documentation](https://malloovia.readthedocs.io/en/latest/usage.html)):

```python
from malloovia import *

# Infrastructure definition
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

# Performances
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

# Workload

# Long term workload prediction of each app, for Phase I
ltwp_app0 = Workload(
    "ltwp0", description="rph to the web server", app=app0,
    values=(201, 203, 180, 220, 190, 211, 199, 204, 500, 200)
)
ltwp_app1 = Workload(
    "ltwp1", description="rph to the database", app=app1,
    values=(2010, 2035, 1807, 2202, 1910, 2110, 1985, 2033, 5050, 1992)
)

# Building the problem for phase I and solving
problem = Problem(
    id="example1",
    name="Example problem",
    workloads=(ltwp_app0, ltwp_app1),
    instance_classes=(m3large_z1, m4xlarge_r1),
    performances=performances
)

phase_i_solution = PhaseI(problem).solve()

# Building the problem for a timeslot in phase II and solving
phase_ii = PhaseII(problem, phase_i_solution)
timeslot_solution = phase_ii.solve_timeslot(
    workloads=(Workload("stwp0", app=app0, description=None, values=(315,)),
               Workload("stwp1", app=app1, description=None, values=(1950,))
               )
    )
    
# Showing the cost and the allocation
print("Cost:", timeslot_solution.solving_stats.optimal_cost)
print(timeslot_solution.allocation._inspect())
```

You can find example problems and solutions in YAML format in the [test data directory](https://github.com/asi-uniovi/malloovia/tree/master/tests/test_data/valid) and in the [GECON 2017 data repository](https://github.com/asi-uniovi/malloovia-data-gecon2017), where you can find [a notebook](https://github.com/asi-uniovi/malloovia-data-gecon2017/blob/master/Malloovia-Gecon2017-data.ipynb) that shows how to compute the solutions from the problems.

Please, refer to [the documentation](https://malloovia.readthedocs.io/) and the he paper ["Cost Minimization of Virtual Machine Allocation in Public Clouds Considering Multiple Applications"](http://www.atc.uniovi.es/personal/joaquin-entrialgo/pdfs/Entrialgo2017-gecon.pdf) for more details.
