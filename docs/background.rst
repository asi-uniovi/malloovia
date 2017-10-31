.. _background:

Background
==========

Conceptually, Malloovia is an extension of `Lloovia <https://github.com/asi-uniovi/lloovia>`_, to allow for multiple applications, each one with a different workload and performance. It is described in paper "`Cost Minimization of Virtual Machine Allocation in Public Clouds Considering Multiple Applications <http://www.atc.uniovi.es/personal/joaquin-entrialgo/pdfs/Entrialgo2017-gecon.pdf>`_" presented at `GECON 2017 <http://2017.gecon-conference.org/>`_.

However, the implementation of Malloovia is not a simple extension of the one of Lloovia. Instead, the code was completely rewritten to obtain a more clean, robust and maintainable implementation. Malloovia is now a standard python package which can be installed with ``pip`` and has very few dependencies (which are automatically installed through ``pip install malloovia``):

* `PuLP <https://pythonhosted.org/PuLP/>`_ is used to create and solve the linear programming problem.
* `ruamel.yaml <https://pypi.python.org/pypi/ruamel.yaml>`_ is used to allow Malloovia to read the problem definition from YAML files, and write the solution to other YAML files, for better interoperability with other tools.
* `jsonschema <https://pypi.python.org/pypi/jsonschema>`_ is used to validate the syntax of the YAML files used.
* `click <http://click.pocoo.org/>`_ and `progress <https://pypi.python.org/pypi/progress>`_ to provide a :ref:`command-line interface <cli>`.

This small number of requirements is an advantage over Lloovia which had dependencies on other "heavy" packages, such as numpy, pandas, matplotlib, jupyter notebooks, etc.

The reason for the small number of dependencies is that Malloovia is more focused. It does not provides tools for analyzing, inspecting or displaying the solution, but only for obtaining it. Since the solution can be stored in the standard YAML format, it can be read, analyzed and displayed it using other tools and libraries, not necessarily python based.


The problem
-----------

The problem to solve is: given a cloud infrastructure composed of different virtual machine types, each one with its own hardware characteristics, and prices, some of them with different pricing schemas, such as discounts for reservation over long periods, and given a set of applications to run on that infrastructure, each one with a different performance on each different VM type, and with a different workload over time, find the number of VMs of each type to activate at each timeslot for each application, so that the expected workload is fulfilled for all applications, the cloud provider limits are not exceeded and the total cost is minimized.


The model
----------------

In order to solve the problem, a great deal of prior information has to be collected, and stored in the model. This model is in essence a set of Python objects which store all relevant information. These objects can be created programmatically from python code, or can be read from external files in YAML format following a custom syntax.

Cloud providers impose limits on the resources that one user can use in each timeslot, but the kind of limits imposed by each provider is different. For example, Azure imposes a limit on the number of CPU cores that can be running during the timeslot, while Amazon imposes limits on the number of VMs of each type inside each region, the total number of on-demand VMs of any type which can be running in the same region, or the total number of reserved VMs of any type which can be running in the same availability zone (one region can contain several availability zones).

To be able to model such a diversity, malloovia introduces the concept of "Instance classes" and "Limiting sets". In addition to this "infrastructure description", Malloovia also needs to know the expected workload for each app, and the performance of each app in each instance class.

*Instance classes*
  One "Instance class" is a particular type of VM running inside a particular region or availability zone. For example, one of Amazon's region is called ``us.east``, and it contains several availability zones called ``us.east_a``, ``us.east_b`` and so on. In all of these availability zones it offers the same set of VM types, for example ``m4.large``, ``m4.xlarge``, ``t2.nano``, etc. Let's consider for example the type ``m4.large``. For Amazon it is a single "VM type", but for Malloovia it is a whole set of "Instance classes", depending the region and zone in which it is deployed. So, a single VM type generates a number of instance classes. It can be called for example ``m4.large_us.east``, ``m4.large_us.east_a``, ``m4.large_us.east_b`` and so on.

  Each instance class is described by several parameters: the number of cores it has, the price (and time unit for the price), the VM type, the limit on the number of VMs of that type allowed inside its region/zone, etc. Some of these parameters are identical for all instance classes originated from the same VM type, but not all of them. For example, the price and limits can be different in different regions.

*Limiting sets*
  A "Limiting set" is a conceptual construct loosely related to regions and availability zones. It allows Malloovia to group different instance classes which share some kind of limit. For example, Amazon imposes a limit on the total number of on-demand VMs which can be running inside a region. Malloovia model this by creating a Limiting set which represents that region and putting all on-demand instance classes which share the region in that limiting set.

  Each Limiting set contains two kinds of limits: on the total number of VMs in that set, and on the total number of cores running in that set. If one of the limits is set to 0, it means "no limit". This way, this model can be used both for Amazon and Azure.

*Workload predictions*
  Each application has one expected workload, which is a sequence of numbers, one per timeslot, which represents the number of requests arriving in the timeslot. The length of the timeslot can be one hour, one minute or one second. Malloovia does not provide any mean to obtain this prediction. Instead, it expects it as part of the problem definition.

*Performances*
   The performance of the app is considered independent on the workload, and dependent only on the instance class in which the app runs. Each instance class is able to sustain a number of requests per timeslot when running one particular app. Then, to capture this information, a table with the performance for each pair (app, instance classes) is enough, along with the time unit of the timeslot.

The combination of the infrastructure description given by *Instance classes* and *Limiting sets*, plus the *Performances* information is what we will call the "System description". The problem to solve by Malloovia is, given a System Description and a Workload Prediction, to find out the allocation of applications to instance classes for each timeslot which minimizes the cost, fulfills the workload, and respects the provider limits.


The solver
------------------

The above information is used by Malloovia to build a linear programming problem, writing it on disk, and calling an external tool (by default `COIN-OR cbc <https://projects.coin-or.org/Cbc>`_) to solve it. The solution given by the solver is read back into python structures and returned by Malloovia.

Malloovia operates in two phases.

* In Phase I, it requires an estimation of the Workload per App for each timeslot along a whole reservation period (for example, if the timeslot is 1 hour and the reservation period is 1 year, this prediction will be made of 8760 values), which we call the LTWP (Long-Term Workload Prediction). This phase will produce the optimal allocation which minimizes the cost, fulfills the predicted workload and respect the limits, for a whole reservation period. In particular, it produces as output the number of reserved instances of each type to purchase at the beginning of the reservation period.

  The optimality of the solution depends of course on the accuracy of the prediction. If the prediction were exact, Phase I would be enough because it produces the required allocation for each timeslot. However, it is unreasonable to expect a perfect prediction, so the actual workload observed on-line, once the system is deployed, will be in general different from the prediction used in Phase I. This is why a Phase II is needed.

* In Phase II, a new optimization problem is run on-line, a few seconds in advance over the next timestlot. This problem uses as input a "System description" (which will be usually the same than the one used in Phase I), the number of reserved instances of each type to use (which is given by the solution of Phase I, since no new reserved instances can be purchased), and the workload prediction for the next timeslot, which is a single number per app, denoted by STWP (Short-Term Workload Prediction).

    Depending on the value of the workload prediction for the next timeslot, we are in one of the following cases:

    * The STWP for the next timeslot was "already seen". This means that the optimal solution for that case is known and it can be simply reused.
    * Otherwise an optimization problem is created for the next timeslot. The result is an optimal allocation which minimizes the cost for the next timeslot, by reusing the reserved instances to fulfill the STWP, instantiating on-demand VMs if necessary.
    * It can be the case that the predicted workload exceeds any value considered in Phase I. In this case the problem could be infeasible, because it could require to hire a number of on-demand VMs which would violate the provider limits. If this happens, it will be impossible to achieve the performance required to fulfill the workload. Malloovia detects this case and changes the strategy for that timeslot only, solving an optimization problem which tries to maximize the percentage of workload served for each app.

    In any case, a new allocation is obtained at this phase, which is used to allocate VMs for the next timeslot.

Although Phase II should happen in real-time (e.g: being executed each timeslot, during a year), Malloovia allows also for a "simulation" of this phase, in which the STWP for each future timeslot is provided in a list, and then Phase II is executed for each element of that list, and the optimal allocation for each timeslot is stored, and global statistics are provided once the list is exhausted.

The solution
------------

The solution is delivered in a python object (which can also be exported into a YAML file), and it is composed by two aspects:

* Statistics about the solver (e.g.: the time required to find the solution, the values of some parameters that influence the accuracy of the solution, the optimality or infeasibility of the problem, etc.) This information is useful to the researcher, to compare Malloovia with other solving methods.

* The optimal allocation, i.e.: the number of VMs of each type for each application. From this allocation it is possible to derive other information, such as the cost per timeslot, the cost per VM type, the cost per App, the performance met per app in each timeslot, etc.

In Phase I, the optimal allocation for each timeslot is usually discarded, because this allocation is only optimal if the LTWP were exact, and it is assumed that it is not the case. So, the useful result of Phase I is the number of reserved instances of each type to be used in Phase II.

