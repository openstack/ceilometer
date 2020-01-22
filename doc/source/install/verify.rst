.. _verify:

Verify operation
~~~~~~~~~~~~~~~~

Verify operation of the Telemetry service. These steps only include the
Image service meters to reduce clutter. Environments with ceilometer
integration for additional services contain more meters.

.. note::

   Perform these steps on the controller node.

.. note::

   The following uses Gnocchi to verify data. Alternatively, data can be
   published to a file backend temporarily by using a ``file://`` publisher.

#. Source the ``admin`` credentials to gain access to
   admin-only CLI commands:

   .. code-block:: console

      $ . admin-openrc

#. List available resource and its metrics:

   .. code-block:: console

      $ gnocchi resource list  --type image
      +--------------------------------------+-------+----------------------------------+---------+--------------------------------------+----------------------------------+----------+----------------------------------+--------------+
      | id                                   | type  | project_id                       | user_id | original_resource_id                 | started_at                       | ended_at | revision_start                   | revision_end |
      +--------------------------------------+-------+----------------------------------+---------+--------------------------------------+----------------------------------+----------+----------------------------------+--------------+
      | a6b387e1-4276-43db-b17a-e10f649d85a3 | image | 6fd9631226e34531b53814a0f39830a9 | None    | a6b387e1-4276-43db-b17a-e10f649d85a3 | 2017-01-25T23:50:14.423584+00:00 | None     | 2017-01-25T23:50:14.423601+00:00 | None         |
      +--------------------------------------+-------+----------------------------------+---------+--------------------------------------+----------------------------------+----------+----------------------------------+--------------+

      $ gnocchi resource show a6b387e1-4276-43db-b17a-e10f649d85a3
      +-----------------------+-------------------------------------------------------------------+
      | Field                 | Value                                                             |
      +-----------------------+-------------------------------------------------------------------+
      | created_by_project_id | aca4db3db9904ecc9c1c9bb1763da6a8                                  |
      | created_by_user_id    | 07b0945689a4407dbd1ea72c3c5b8d2f                                  |
      | creator               | 07b0945689a4407dbd1ea72c3c5b8d2f:aca4db3db9904ecc9c1c9bb1763da6a8 |
      | ended_at              | None                                                              |
      | id                    | a6b387e1-4276-43db-b17a-e10f649d85a3                              |
      | metrics               | image.download: 839afa02-1668-4922-a33e-6b6ea7780715              |
      |                       | image.serve: 1132e4a0-9e35-4542-a6ad-d6dc5fb4b835                 |
      |                       | image.size: 8ecf6c17-98fd-446c-8018-b741dc089a76                  |
      | original_resource_id  | a6b387e1-4276-43db-b17a-e10f649d85a3                              |
      | project_id            | 6fd9631226e34531b53814a0f39830a9                                  |
      | revision_end          | None                                                              |
      | revision_start        | 2017-01-25T23:50:14.423601+00:00                                  |
      | started_at            | 2017-01-25T23:50:14.423584+00:00                                  |
      | type                  | image                                                             |
      | user_id               | None                                                              |
      +-----------------------+-------------------------------------------------------------------+


#. Download the CirrOS image from the Image service:

   .. code-block:: console

      $ IMAGE_ID=$(glance image-list | grep 'cirros' | awk '{ print $2 }')
      $ glance image-download $IMAGE_ID > /tmp/cirros.img

#. List available meters again to validate detection of the image
   download:

   .. code-block:: console

      $ gnocchi measures show 839afa02-1668-4922-a33e-6b6ea7780715
      +---------------------------+-------------+-----------+
      | timestamp                 | granularity |     value |
      +---------------------------+-------------+-----------+
      | 2017-01-26T15:35:00+00:00 |       300.0 | 3740163.0 |
      +---------------------------+-------------+-----------+

#. Remove the previously downloaded image file ``/tmp/cirros.img``:

   .. code-block:: console

      $ rm /tmp/cirros.img
