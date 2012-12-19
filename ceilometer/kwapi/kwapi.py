# -*- coding: utf-8 -*-

from keystoneclient.v2_0 import client as ksclient
import requests

from ceilometer import counter
from ceilometer.central import plugin
from ceilometer.collector import meter
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils

class KwapiClient():
    """Kwapi API client."""
    
    def __init__(self, url, token=None):
        """Initializes client."""
        self.url = url
        self.token = token
    
    def list_probes(self):
        """Returns a list of dicts describing all probes."""
        probes_url = self.url + '/probes/'
        headers = {}
        if self.token is not None:
            headers = {'X-Auth-Token': self.token}
        request = requests.get(probes_url, headers=headers)
        message = request.json
        
        probe_list = []
        
        if meter.verify_signature(message, cfg.CONF['metering_secret']):
            probes = message['probes']
            for key, value in probes.iteritems():
                probe_dict = value
                probe_dict['id'] = key
                probe_list.append(probe_dict)
            
        return probe_list

class _Base(plugin.CentralPollster):
    """Base class for the Kwapi pollster, derived from CentralPollster."""
    
    @staticmethod
    def get_kwapi_client():
        """Returns a KwapiClient configured with the proper url and token."""
        keystone = ksclient.Client(username=cfg.CONF.os_username,
                            password=cfg.CONF.os_password,
                            tenant_id=cfg.CONF.os_tenant_id,
                            tenant_name=cfg.CONF.os_tenant_name,
                            auth_url=cfg.CONF.os_auth_url)
        endpoint = keystone.service_catalog.url_for(service_type='metering', endpoint_type='internalURL')
        return KwapiClient(endpoint, keystone.auth_token)
    
    def iter_probes(self):
        """Iterate over all probes."""
        client = self.get_kwapi_client()
        return client.list_probes()

class KwapiPollster(_Base):
    """Kwapi pollster derived from the base class."""
    
    LOG = log.getLogger(__name__ + '.kwapi')
    
    def get_counters(self, manager, context):
        """Returns all counters."""
        for probe in self.iter_probes():
            yield counter.Counter(
                name='kwapi',
                type=counter.TYPE_CUMULATIVE,
                volume=probe['kwh'],
                user_id=None,
                project_id=None,
                resource_id=probe['id'],
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata={
                        'timestamp': probe['timestamp'],
                        'w': probe['w']
                    }
            )
