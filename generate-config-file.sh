#!/bin/sh
oslo-config-generator --output-file etc/ceilometer/ceilometer.conf \
    --namespace ceilometer \
    --namespace oslo.concurrency \
    --namespace oslo.db \
    --namespace oslo.log \
    --namespace oslo.messaging \
    --namespace oslo.policy \
    --namespace oslo.service.service \
    --namespace keystonemiddleware.auth_token
