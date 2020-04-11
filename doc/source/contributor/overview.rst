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
Ceilometer: become a standard way to meter, regardless of the
purpose of the collection. This data can then be pushed to any set of targets
using provided publishers mentioned in `pipeline-publishers` section.

.. _increasing number of meters: https://docs.openstack.org/ceilometer/latest/contributor/measurements.html

Metering
========

If you divide a billing process into a 3 step process, as is commonly done in
the telco industry, the steps are:

1. :term:`metering`
2. :term:`rating`
3. :term:`billing`

Ceilometer's initial goal was, and still is, strictly limited to step
one. This is a choice made from the beginning not to go into rating or billing,
as the variety of possibilities seemed too large for the project to ever
deliver a solution that would fit everyone's needs, from private to public
clouds. This means that if you are looking at this project to solve your
billing needs, this is the right way to go, but certainly not the end of the
road for you.
