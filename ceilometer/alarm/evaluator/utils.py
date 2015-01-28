#
# Copyright 2014 Red Hat, Inc
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

import math


def mean(s, key=lambda x: x):
    """Calculate the mean of a numeric list."""
    count = float(len(s))
    if count:
        return math.fsum(map(key, s)) / count
    return 0.0


def deltas(s, key, m=None):
    """Calculate the squared distances from mean for a numeric list."""
    m = m or mean(s, key)
    return [(key(i) - m) ** 2 for i in s]


def variance(s, key, m=None):
    """Calculate the variance of a numeric list."""
    return mean(deltas(s, key, m))


def stddev(s, key, m=None):
    """Calculate the standard deviation of a numeric list."""
    return math.sqrt(variance(s, key, m))


def outside(s, key, lower=0.0, upper=0.0):
    """Determine if value falls outside upper and lower bounds."""
    v = key(s)
    return v < lower or v > upper


def anomalies(s, key, lower=0.0, upper=0.0):
    """Separate anomalous data points from the in-liers."""
    inliers = []
    outliers = []
    for i in s:
        if outside(i, key, lower, upper):
            outliers.append(i)
        else:
            inliers.append(i)
    return inliers, outliers
