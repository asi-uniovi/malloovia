=======
History
=======

0.1.0 (2017-07-24)
------------------

* First release on PyPI.

0.2.0 (2017-07-27)
------------------

* `from malloovia import *` imports all relevant classes and methods.
* `read_problems_from_github()` added.
* Integration with Travis-CI and ReadTheDocs.
* Working on the documentation.
* Modified YAML schema of the Solutions.

0.3.0 (2017-07-31)
------------------

* Much improved documentation. Windows installation covered.
* Command-line interface
* Changed from PyYAML to ruamel.yaml, much faster
* Read from YAML now accepts gzipped files too
* Some bugs fixed in the schema

1.0.0 (2017-11-01)
------------------

* Incompatible API change: it is required to specify ``time_unit`` in
  ``InstanceClass``, ``PerformanceSet`` and ``Workload`` classes, in order to
  clarify the time unit for price, performance and workload timeslots.
* Added utility function to read solutions from yaml files.
* Revised documentation and code quality. Improved README for github.
* Minor bugfixes.

1.0.1 (2018-01-12)
------------------

* Bugfix to make all malloovia classes pickable, allowing for multiprocessing.

1.1.0 (2018-03-16)
------------------

* New class ``PhaseIIGuided`` which allows to solve a single timeslot using
  a given allocation which specifies the minimum number of VMs to keep running.
