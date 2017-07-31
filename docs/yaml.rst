.. _yaml:

Yaml format
===========

Descriptions of the cloud infrastructure, performances and workload predictions can be built from python using Malloovia's API, as described in :ref:`usage` section, but they can be also stored in yaml files, which allows the interoperability with other tools.

Malloovia provides functions to read problems from YAML files, and to store the solutions found by the solver in YAML files.

.. warning::

   This section of the documentation will describe the YAML format. It is not yet written. Meanwhile you can see some `examples in Malloovia repository <https://github.com/asi-uniovi/malloovia/tree/master/tests/test_data/problems>`_, and the snippets included in :ref:`usage` section.
   You can also refer to the :ref:`schema` below.


.. _schema:

Schema
------

Here is the schema which describes malloovia's format. It is written as YAML, since it is easier to read, but it is compatible with the `json schema standard <http://json-schema.org/>`_.

.. container:: toggle

    .. container:: header

        **Show/hide YAML schema**

    .. literalinclude:: ../malloovia/malloovia.schema.yaml
       :language: yaml
