=========
 Web API
=========

.. toctree::
   :maxdepth: 2

   v2

You can get API version list via request to endpoint root path. For example::

  curl -H "X-AUTH-TOKEN: fa2ec18631f94039a5b9a8b4fe8f56ad" http://127.0.0.1:8777

Sample response::

  {
      "versions": {
          "values": [
              {
                  "id": "v2",
                  "links": [
                      {
                          "href": "http://127.0.0.1:8777/v2",
                          "rel": "self"
                      },
                      {
                          "href": "http://docs.openstack.org/",
                          "rel": "describedby",
                          "type": "text/html"
                      }
                  ],
                  "media-types": [
                      {
                          "base": "application/json",
                          "type": "application/vnd.openstack.telemetry-v2+json"
                      },
                      {
                          "base": "application/xml",
                          "type": "application/vnd.openstack.telemetry-v2+xml"
                      }
                  ],
                  "status": "stable",
                  "updated": "2013-02-13T00:00:00Z"
              }
          ]
      }
  }
