==============
pytelegrafhttp
==============
A module to provide Telegraf with metrics scraped from HTTP.

This library scrapes metrics from HTTP pages and sends the results to Telegraf via a local UDP socket. Writen in Python
for ease of development and accesses Telegraf via the `Pytelegraf <https://github.com/paksu/pytelegraf/>`_ plugin.

Though a telegraf input plugin for getting metrics from an HTTP server exists (`HTTP JSON Input Plugin
<https://github.com/influxdata/telegraf/tree/master/plugins/inputs/httpjson>`_), it currently only supports restful
APIs that speak JSON, along with typical JSON API authentication methods. This project closes the gap by supporting
authenticated logins for pages that do not have a proper restful HTTP JSON-speaking API, such as human-consumable PHP
pages only accessible via login.