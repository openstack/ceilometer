=========
 Web API
=========

.. note::

   Gnocchi provides a more responsive API when statistical capabilities rather
   than full-resolution datapoints are required. The REST API for Gnocchi is
   captured here_.

.. _here: http://gnocchi.xyz/rest.html

.. toctree::
   :maxdepth: 2

   v2

You can get API version list via request to endpoint root path. For example::

    $ curl -H "X-AUTH-TOKEN: fa2ec18631f94039a5b9a8b4fe8f56ad" http://127.0.0.1:8777

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
                          "href": "https://docs.openstack.org/",
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
