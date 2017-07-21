* Enable periodic usage statistics relating to block storage. To use it, you
  must run this command in the following format:

  .. code-block:: console

     $ cinder-volume-usage-audit  --start_time='YYYY-MM-DD HH:MM:SS' \
       --end_time='YYYY-MM-DD HH:MM:SS' --send_actions

  This script outputs what volumes or snapshots were created, deleted, or
  exists in a given period of time and some information about these
  volumes or snapshots.

  Using this script via cron you can get notifications periodically, for
  example, every 5 minutes::

       */5 * * * * /path/to/cinder-volume-usage-audit --send_actions
