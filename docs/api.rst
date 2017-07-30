.. _api:

==================================
High level API
==================================

Infrastructure specification
----------------------------

The data about the cloud infrastructure is stored in different entities:

* :class:`malloovia.LimitingSet` defines some constraints imposed by the cloud
  provider about the maximum number of virtual machines or cores which can
  be running in a region or availability zone.
* :class:`malloovia.InstanceClass` represents one particular type of virtual
  machine to be deployed in one particular cloud provider and region/availability
  zone. It holds information about the price, limits and whether it is a
  reserved (prepaid for a whole reservation period) or on-demand (pay-per-use).


Example:

.. testcode::

    region1 = LimitingSet("region1", name="us.east", max_vms=20)
    zone1 =  LimitingSet("region1_z1", name="us.east_a", max_vms=20)
    m3large_z1 = InstanceClass(
        "m3large_z1", name="reserved m3.large in us.east_a",
        limiting_sets=(zone1,), is_reserved=True,
        price=7, max_vms=20)
    m4xlarge_r1 = InstanceClass(
        "m4xlarge_r1", name="ondemand m4.xlarge in us.east",
        limiting_sets=(region1,), is_reserved=False,
        price=10, max_vms=10)

.. container:: toggle

    .. container:: header

        **Show/hide YAML version**

    .. code-block:: yaml

        Limiting_sets:
            - &region1
                id: region1
                name: us.east
                max_vms: 20
            - &region1_z1
                id: region1_z1
                name: us.east_a
                max_vms: 20

        Instance_classes:
            - &m3large_z1
                id: m3large_z1
                name: reserved m3.large in us.east_a
                limiting_sets: [*region1_z1]
                is_reserved: true
                price: 7
                max_vms: 20
            - &m4xlarge_r1
                id: m4xlarge_r1
                name: ondemand m4.xlarge in us.east
                limiting_sets: [*region1]
                is_reserved: false
                price: 10
                max_vms: 10



Workload specification
----------------------

Malloovia deals with different applications, each one characterized by its own
workload. The solving algorithm requires a prediction of the workload for each
application. In Phase I, there is a long-term workload prediction (LTWP) which
contains the expected workload for each timeslot in the whole reservation period.
In Phase II there is a short-term workload prediction (STWO) which contains the
expected workload for the next timeslot only.

A :class:`malloovia.App` is an abstraction of a disk image containing
the software to be run in one instance class. Currently it is defined only by
its name.

A :class:`malloovia.Workload` object contains either the LTWP or the STWP,
as well as the application related to that workload and other
metadata. Example:


.. warning::

   Work in progress


Performance specification
-------------------------

In order to guarantee that the solution fulfills the expected workload, the
solver needs to know the performance of each application on each different
instance class.





Classes and methods of the API
------------------------------

.. automodule:: malloovia
    :members:
    :undoc-members:
    :imported-members:
