# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from nova.rpc import impl_kombu


class Connection(impl_kombu.Connection):
    """A Kombu connection that does not use the AMQP Proxy class when
    creating a consumer, so we can decode the message ourself."""

    def create_consumer(self, topic, proxy, fanout=False):
        """Create a consumer without using ProxyCallback."""
        if fanout:
            self.declare_fanout_consumer(topic, proxy)
        else:
            self.declare_topic_consumer(topic, proxy)
