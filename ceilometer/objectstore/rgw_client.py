#
# Copyright 2015 Reliance Jio Infocomm Ltd
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


from collections import namedtuple

from awscurl import awscurl

from urllib import parse as urlparse

from ceilometer.i18n import _


class RGWAdminAPIFailed(Exception):
    pass


class RGWAdminClient:
    Bucket = namedtuple('Bucket', 'name, num_objects, size')

    def __init__(self, endpoint, access_key, secret_key, implicit_tenants):
        self.access_key = access_key
        self.secret = secret_key
        self.endpoint = endpoint
        self.hostname = urlparse.urlparse(endpoint).netloc
        self.implicit_tenants = implicit_tenants

    def _make_request(self, path, req_params):
        uri = f"{self.endpoint}/{path}"
        if req_params:
            uri = f"{uri}?"
            # Append req_params content to the uri
            for i, (key, value) in enumerate(req_params.items()):
                if i == len(req_params) - 1:
                    uri = uri + key + "=" + value
                else:
                    uri = uri + key + "=" + value + "&"

        # Data to be sent with request POST type,
        # otherwise provide an empty string
        data = ""
        service = "s3"
        method = "GET"
        # Default region, in the case of radosgw either set
        # the value to your zonegroup name or keep the default region.
        # With a single Ceph zone-group, there's no need to customize
        # this value.
        region = "us-east-1"
        headers = {'Accept': 'application/json'}

        r = awscurl.make_request(method, service, region, uri, headers, data,
                                 self.access_key, self.secret, None, False,
                                 False)

        if r.status_code != 200:
            raise RGWAdminAPIFailed(
                _('RGW AdminOps API returned %(status)s %(reason)s') %
                {'status': r.status_code, 'reason': r.reason})
        if not r.text:
            return {}

        return r.json()

    def get_bucket(self, tenant_id):
        if self.implicit_tenants:
            rgw_uid = tenant_id + "$" + tenant_id
        else:
            rgw_uid = tenant_id
        path = "bucket"
        req_params = {"uid": rgw_uid, "stats": "true"}
        json_data = self._make_request(path, req_params)
        stats = {'num_buckets': 0, 'buckets': [], 'size': 0, 'num_objects': 0}
        stats['num_buckets'] = len(json_data)
        for it in json_data:
            for v in it["usage"].values():
                stats['num_objects'] += v["num_objects"]
                stats['size'] += v["size_kb"]
                stats['buckets'].append(self.Bucket(it["bucket"],
                                                    v["num_objects"],
                                                    v["size_kb"]))
        return stats

    def get_usage(self, tenant_id):
        if self.implicit_tenants:
            rgw_uid = tenant_id + "$" + tenant_id
        else:
            rgw_uid = tenant_id
        path = "usage"
        req_params = {"uid": rgw_uid}
        json_data = self._make_request(path, req_params)
        usage_data = json_data["summary"]
        return sum(it["total"]["ops"] for it in usage_data)
