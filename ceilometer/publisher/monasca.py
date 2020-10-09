#
# Copyright 2015 Hewlett Packard
# (c) Copyright 2018 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from futurist import periodics

import os
import threading
import time

from oslo_log import log

import ceilometer
from ceilometer import monasca_client as mon_client
from ceilometer import publisher
from ceilometer.publisher.monasca_data_filter import MonascaDataFilter

from monascaclient import exc
import traceback

# Have to use constants rather than conf to satisfy @periodicals
BATCH_POLLING_INTERVAL = 5
BATCH_RETRY_INTERVAL = 60

LOG = log.getLogger(__name__)


class MonascaPublisher(publisher.ConfigPublisherBase):
    """Publisher to publish samples to monasca using monasca-client.

    Example URL to place in pipeline.yaml:
        - monasca://http://192.168.10.4:8070/v2.0
    """
    def __init__(self, conf, parsed_url):
        super(MonascaPublisher, self).__init__(conf, parsed_url)

        # list to hold metrics to be published in batch (behaves like queue)
        self.metric_queue = []
        self.time_of_last_batch_run = time.time()

        self.mon_client = mon_client.Client(self.conf, parsed_url)
        self.mon_filter = MonascaDataFilter(self.conf)

        # add flush_batch function to periodic callables
        periodic_callables = [
            # The function to run + any automatically provided
            # positional and keyword arguments to provide to it
            # everytime it is activated.
            (self.flush_batch, (), {}),
        ]

        if self.conf.monasca.retry_on_failure:
            # list to hold metrics to be re-tried (behaves like queue)
            self.retry_queue = []
            # list to store retry attempts for metrics in retry_queue
            self.retry_counter = []

            # add retry_batch function to periodic callables
            periodic_callables.append((self.retry_batch, (), {}))

        if self.conf.monasca.archive_on_failure:
            archive_path = self.conf.monasca.archive_path
            if not os.path.exists(archive_path):
                archive_path = self.conf.find_file(archive_path)

            self.archive_handler = publisher.get_publisher(
                self.conf,
                'file://' +
                str(archive_path),
                'ceilometer.sample.publisher')

        # start periodic worker
        self.periodic_worker = periodics.PeriodicWorker(periodic_callables)
        self.periodic_thread = threading.Thread(
            target=self.periodic_worker.start)
        self.periodic_thread.daemon = True
        self.periodic_thread.start()

    def _publish_handler(self, func, metrics, batch=False):
        """Handles publishing and exceptions that arise."""

        try:
            metric_count = len(metrics)
            if batch:
                func(**{'jsonbody': metrics})
            else:
                func(**metrics[0])
            LOG.info('Successfully published %d metric(s)' % metric_count)
        except mon_client.MonascaServiceException:
            # Assuming atomicity of create or failure - meaning
            # either all succeed or all fail in a batch
            LOG.error('Metric create failed for %(count)d metric(s) with'
                      ' name(s) %(names)s ' %
                      ({'count': len(metrics),
                        'names': ','.join([metric['name']
                                           for metric in metrics])}))
            if self.conf.monasca.retry_on_failure:
                # retry payload in case of internal server error(500),
                # service unavailable error(503),bad gateway (502) or
                # Communication Error

                # append failed metrics to retry_queue
                LOG.debug('Adding metrics to retry queue.')
                self.retry_queue.extend(metrics)
                # initialize the retry_attempt for the each failed
                # metric in retry_counter
                self.retry_counter.extend(
                    [0 * i for i in range(metric_count)])
            else:
                if hasattr(self, 'archive_handler'):
                    self.archive_handler.publish_samples(None, metrics)
        except Exception:
            LOG.info(traceback.format_exc())
            if hasattr(self, 'archive_handler'):
                self.archive_handler.publish_samples(None, metrics)

    def publish_samples(self, samples):
        """Main method called to publish samples."""

        for sample in samples:
            metric = self.mon_filter.process_sample_for_monasca(sample)
            # In batch mode, push metric to queue,
            # else publish the metric
            if self.conf.monasca.batch_mode:
                LOG.debug('Adding metric to queue.')
                self.metric_queue.append(metric)
            else:
                LOG.info('Publishing metric with name %(name)s and'
                         ' timestamp %(ts)s to endpoint.' %
                         ({'name': metric['name'],
                           'ts': metric['timestamp']}))

                self._publish_handler(self.mon_client.metrics_create, [metric])

    def is_batch_ready(self):
        """Method to check if batch is ready to trigger."""

        previous_time = self.time_of_last_batch_run
        current_time = time.time()
        elapsed_time = current_time - previous_time

        if elapsed_time >= self.conf.monasca.batch_timeout and len(self.
           metric_queue) > 0:
            LOG.info('Batch timeout exceeded, triggering batch publish.')
            return True
        else:
            if len(self.metric_queue) >= self.conf.monasca.batch_count:
                LOG.info('Batch queue full, triggering batch publish.')
                return True
            else:
                return False

    @periodics.periodic(BATCH_POLLING_INTERVAL)
    def flush_batch(self):
        """Method to flush the queued metrics."""
        # print "flush batch... %s" % str(time.time())
        if self.is_batch_ready():
            # publish all metrics in queue at this point
            batch_count = len(self.metric_queue)

            LOG.info("batch is ready: batch_count %s" % str(batch_count))

            self._publish_handler(self.mon_client.metrics_create,
                                  self.metric_queue[:batch_count],
                                  batch=True)

            self.time_of_last_batch_run = time.time()
            # slice queue to remove metrics that
            # published with success or failed and got queued on
            # retry queue
            self.metric_queue = self.metric_queue[batch_count:]

    def is_retry_ready(self):
        """Method to check if retry batch is ready to trigger."""

        if len(self.retry_queue) > 0:
            LOG.info('Retry queue has items, triggering retry.')
            return True
        else:
            return False

    @periodics.periodic(BATCH_RETRY_INTERVAL)
    def retry_batch(self):
        """Method to retry the failed metrics."""
        # print "retry batch...%s" % str(time.time())
        if self.is_retry_ready():
            retry_count = len(self.retry_queue)

            # Iterate over the retry_queue to eliminate
            # metrics that have maxed out their retry attempts
            for ctr in range(retry_count):
                if self.retry_counter[ctr] > self.conf.\
                        monasca.batch_max_retries:
                    if hasattr(self, 'archive_handler'):
                        self.archive_handler.publish_samples(
                            None,
                            [self.retry_queue[ctr]])
                    LOG.info('Removing metric %s from retry queue.'
                             ' Metric retry maxed out retry attempts' %
                             self.retry_queue[ctr]['name'])
                    del self.retry_queue[ctr]
                    del self.retry_counter[ctr]

            # Iterate over the retry_queue to retry the
            # publish for each metric.
            # If an exception occurs, the retry count for
            # the failed metric is incremented.
            # If the retry succeeds, remove the metric and
            # the retry count from the retry_queue and retry_counter resp.
            ctr = 0
            while ctr < len(self.retry_queue):
                try:
                    LOG.info('Retrying metric publish from retry queue.')
                    self.mon_client.metrics_create(**self.retry_queue[ctr])
                    # remove from retry queue if publish was success
                    LOG.info('Retrying metric %s successful,'
                             ' removing metric from retry queue.' %
                             self.retry_queue[ctr]['name'])
                    del self.retry_queue[ctr]
                    del self.retry_counter[ctr]
                except exc.ClientException:
                    LOG.error('Exception encountered in retry. '
                              'Batch will be retried in next attempt.')
                    # if retry failed, increment the retry counter
                    self.retry_counter[ctr] += 1
                    ctr += 1

    def flush_to_file(self):
        # TODO(persist maxed-out metrics to file)
        pass

    def publish_events(self, events):
        """Send an event message for publishing

        :param events: events from pipeline after transformation
        """
        raise ceilometer.NotImplementedError
