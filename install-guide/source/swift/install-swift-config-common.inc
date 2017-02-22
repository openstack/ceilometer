Configure Object Storage to use Telemetry
-----------------------------------------

Perform these steps on the controller and any other nodes that
run the Object Storage proxy service.

* Edit the ``/etc/swift/proxy-server.conf`` file
  and complete the following actions:

  * In the ``[filter:keystoneauth]`` section, add the
    ``ResellerAdmin`` role:

    .. code-block:: ini

       [filter:keystoneauth]
       ...
       operator_roles = admin, user, ResellerAdmin

  * In the ``[pipeline:main]`` section, add ``ceilometer``:

    .. code-block:: ini

       [pipeline:main]
       pipeline = catch_errors gatekeeper healthcheck proxy-logging cache container_sync bulk ratelimit authtoken keystoneauth container-quotas account-quotas slo dlo versioned_writes proxy-logging ceilometer proxy-server

  * In the ``[filter:ceilometer]`` section, configure notifications:

    .. code-block:: ini

       [filter:ceilometer]
       paste.filter_factory = ceilometermiddleware.swift:filter_factory
       ...
       control_exchange = swift
       url = rabbit://openstack:RABBIT_PASS@controller:5672/
       driver = messagingv2
       topic = notifications
       log_level = WARN

    Replace ``RABBIT_PASS`` with the password you chose for the
    ``openstack`` account in ``RabbitMQ``.
