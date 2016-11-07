#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2014 Hewlett-Packard Company
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

"""Access Control Lists (ACL's) control access the API server."""

import pecan


def _has_rule(name):
    return name in pecan.request.enforcer.rules.keys()


def enforce(policy_name, request):
    """Checks authorization of a rule against the request.

    :param request: HTTP request
    :param policy_name: the policy name to validate authz against.


    """

    rule_method = "telemetry:" + policy_name
    headers = request.headers

    policy_dict = dict()
    policy_dict['roles'] = headers.get('X-Roles', "").split(",")
    policy_dict['user_id'] = (headers.get('X-User-Id'))
    policy_dict['project_id'] = (headers.get('X-Project-Id'))

    # maintain backward compat with Juno and previous by allowing the action if
    # there is no rule defined for it
    if ((_has_rule('default') or _has_rule(rule_method)) and
            not pecan.request.enforcer.enforce(rule_method, {}, policy_dict)):
        pecan.core.abort(status_code=403, detail='RBAC Authorization Failed')


# TODO(fabiog): these methods are still used because the scoping part is really
# convoluted and difficult to separate out.

def get_limited_to(headers):
    """Return the user and project the request should be limited to.

    :param headers: HTTP headers dictionary
    :return: A tuple of (user, project), set to None if there's no limit on
    one of these.

    """

    policy_dict = dict()
    policy_dict['roles'] = headers.get('X-Roles', "").split(",")
    policy_dict['user_id'] = (headers.get('X-User-Id'))
    policy_dict['project_id'] = (headers.get('X-Project-Id'))

    # maintain backward compat with Juno and previous by using context_is_admin
    # rule if the segregation rule (added in Kilo) is not defined
    rule_name = 'segregation' if _has_rule(
        'segregation') else 'context_is_admin'
    if not pecan.request.enforcer.enforce(rule_name,
                                          {},
                                          policy_dict):
        return headers.get('X-User-Id'), headers.get('X-Project-Id')

    return None, None


def get_limited_to_project(headers):
    """Return the project the request should be limited to.

    :param headers: HTTP headers dictionary
    :return: A project, or None if there's no limit on it.

    """
    return get_limited_to(headers)[1]
