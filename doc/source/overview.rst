========
Overview
========

Objectives
==========

The Ceilometer project was started in 2012 with one simple goal in mind: to
provide an infrastructure to collect any information needed regarding
OpenStack projects. It was designed so that rating engines could use this
single source to transform events into billable items which we
label as "metering".

As the project started to come to life, collecting an
`increasing number of meters`_ across multiple projects, the OpenStack
community started to realize that a secondary goal could be added to
Ceilometer: become a standard way to collect meter, regardless of the
purpose of the collection.  For example, Ceilometer can now publish information
for monitoring, debugging and graphing tools in addition or in parallel to the
metering backend. We labelled this effort as "multi-publisher".

.. _increasing number of meters: http://docs.openstack.org/developer/ceilometer/measurements.html

Metering
========

If you divide a billing process into a 3 step process, as is commonly done in
the telco industry, the steps are:

1. :term:`Metering`
2. :term:`Rating`
3. :term:`Billing`

Ceilometer's initial goal was, and still is, strictly limited to step
one. This is a choice made from the beginning not to go into rating or billing,
as the variety of possibilities seemed too large for the project to ever
deliver a solution that would fit everyone's needs, from private to public
clouds. This means that if you are looking at this project to solve your
billing needs, this is the right way to go, but certainly not the end of the
road for you. Once Ceilometer is in place on your OpenStack deployment, you
will still have several things to do before you can produce a bill for your
customers. One of you first task could be: finding the right queries within the
Ceilometer API to extract the information you need for your very own rating
engine.

.. seealso::

   * http://wiki.openstack.org/EfficientMetering/ArchitectureProposalV1
   * http://wiki.openstack.org/EfficientMetering#Architecture
