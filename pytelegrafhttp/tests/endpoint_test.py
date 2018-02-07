from pytelegrafhttp.endpoint import Endpoint
from pytelegrafhttp.util import check_online
from pytelegrafhttp.clock import now
from pytelegrafhttp import scrape
from unittest import TestCase
import re
from datetime import timedelta


class EndpointTest(TestCase):

	def setUp(self):
		self.endpoint = Endpoint('/myuri/endpoint', re.compile('F@H Miss% shows the percentage of requests'))

	def test_single_client(self):
		text = _create_body_text(
			dict(
				id='12345',
				name='flandre',
				files=61234,
				trust=456,
				quality=3953,
				hitrate=2.6,
				hathrate=1,
				online=True
			)
		)
		metric = self.endpoint.scrape_metric(_client_stats_metric, text)[0]
		v, t = metric['values'], metric['tags']

		# values
		self.assertTrue(v['online'])
		self.assertEqual(v['files'], 61234)
		self.assertEqual(v['trust'], 456)
		self.assertEqual(v['quality'], 3953)
		self.assertEqual(v['hitrate'], 2.6)
		self.assertEqual(v['hathrate'], 1.0)

		# tags
		self.assertEqual(t['host'], 'flandre')
		self.assertEqual(t['client-id'], '12345')

	def test_client_toolong_not_connected(self):
		now_time = now()
		ts = now_time - timedelta(minutes=6)
		if ts.day != now_time.day:
			time_str = "Yesterday, "
		else:
			time_str = "Today, "
		time_str += str(ts.hour) + ':' + str(ts.minute)
		text = _create_body_text(
			dict(
				online=True,
				last_seen=time_str
			)
		)

		v = self.endpoint.scrape_metric(_client_stats_metric, text)[0]['values']

		self.assertFalse(v['online'])

	def test_client_offline(self):
		text = _create_body_text(
			dict(
				id='12345',
				name='flandre',
				files=61234,
				trust=456,
				quality=3953,
				hitrate=2.6,
				hathrate=1,
				online=False
			)
		)

		v = self.endpoint.scrape_metric(_offline_client_stats_metric, text)[0]['values']

		self.assertNotIn('trust', v)
		self.assertNotIn('quality', v)
		self.assertNotIn('hitrate', v)
		self.assertNotIn('hathrate', v)
		self.assertEqual(v['files'], 61234)

	def test_regions(self):
		text = _create_body_text(regions=[
			dict(
				region='Asia and Nearby Regions',
				load_mb=612,
				miss_rate=2.45,
				coverage=14.5,
				hits_per_gb=0.2942,
				quality=4695
			)
		])

		metric = self.endpoint.scrape_metric(_network_stats_metric, text)[0]
		v, t = metric['values'], metric['tags']

		# values
		self.assertEqual(v['load'], 612)
		self.assertEqual(v['miss-rate'], 2.45)
		self.assertEqual(v['coverage'], 14.5)
		self.assertEqual(v['hits-per-gb'], 0.2942)
		self.assertEqual(v['quality'], 4695)

		# tags
		self.assertEqual(t['region'], 'Asia and Nearby Regions')


_network_stats_metric = scrape.parse_config_metrics([{
	'dest': 'hath-net',
	'name': 'hath-net',
	'regex': [
		r'<td>([^<]*)</td>\s*',
		r'<td [^>]*>[^ ]+ Gbit/s</td>\s*',
		r'<td [^>]*>=</td>\s*',
		r'<td [^>]*>([^ ]+) MB/s</td>\s*',
		r'<td [^>]*>([^ ]+) %</td>\s*',
		r'<td [^>]*>([^<]+)</td>\s*',
		r'<td [^>]*>([^<]+)</td>\s*',
		r'<td [^>]*>([^<]+)</td>',
	],
	'values': [
		{'name': 'load', 'conversion': int, 'type': 'CAPTURE-2'},
		{'name': 'miss-rate', 'conversion': float, 'type': 'CAPTURE-3'},
		{'name': 'coverage', 'conversion': float, 'type': 'CAPTURE-4'},
		{'name': 'hits-per-gb', 'conversion': float, 'type': 'CAPTURE-5'},
		{'name': 'quality', 'conversion': int, 'type': 'CAPTURE-6'}
	],
	'tags': {'region': 'CAPTURE-1'}
}], '')[0]

_client_stats_metric = scrape.parse_config_metrics([{
	'dest': 'hath-client-net-stats',
	'name': 'hath-health',
	'regex': [
		r'<tr>\s*',
		r'<td><a [^>]*>([^<]+)</a></td>\s*',
		r'<td>([^<]+)</td>\s*',
		r'<td [^>]*>Online</td>\s*',
		r'<td>[^<]*</td>\s*',
		r'<td>([^<]*)</td>\s*',
		r'<td>([^<]+)</td>\s*',
		r'<td [^>]*>[^<]+</td>\s*',
		r'<td>[^<]*</td>\s*',
		r'<td>[^<]*</td>\s*',
		r'<td>[^<]*</td>\s*',
		r'<td [^>]*>([^<]+)</td>\s*',
		r'<td>([^<]+)</td>\s*',
		r'<td>([^ ]+) / min</td>\s*',
		r'<td>([^ ]+) / day</td>\s*',
	],
	'values': [
		{'name': 'online', 'conversion': lambda last: check_online(last, max_minutes=5), 'type': 'CAPTURE-3'},
		{'name': 'files', 'conversion': lambda x: int(x.replace(',', '')), 'type': 'CAPTURE-4'},
		{'name': 'trust', 'conversion': int, 'type': 'CAPTURE-5'},
		{'name': 'quality', 'conversion': int, 'type': 'CAPTURE-6'},
		{'name': 'hitrate', 'conversion': float, 'type': 'CAPTURE-7'},
		{'name': 'hathrate', 'conversion': float, 'type': 'CAPTURE-8'}
	],
	'tags': {
		'host': 'CAPTURE-1',
		'client-id': 'CAPTURE-2',
	}
}], '')[0]

_offline_client_stats_metric = scrape.parse_config_metrics([{
	'dest': 'hath-client-net-stats',
	'name': 'hath-health',
	'regex': [
		r'<tr>\s*',
		r'<td><a [^>]*>([^<]+)</a></td>\s*',
		r'<td>([^<]+)</td>\s*',
		r'<td [^>]*>Offline</td>\s*',
		r'<td>[^<]*</td>\s*',
		r'<td>[^<]*</td>\s*',
		r'<td>([^<]+)</td>\s*',
		r'<td [^>]*>Not available when offline</td>\s*'
	],
	'values': [
		{'name': 'online', 'conversion': False, 'type': 'VALUE'},
		{'name': 'files', 'conversion': lambda x: int(x.replace(',', '')), 'type': 'CAPTURE-3'}
	],
	'tags': {
		'host': 'CAPTURE-1',
		'client-id': 'CAPTURE-2',
	}
}], '')[0]


def _create_network_text(**kwargs):
	region = kwargs.get('region', "region-name")
	load_gb = kwargs.get('load_gb', None)
	load_mb = kwargs.get('load_mb', None)
	if load_mb is None and load_gb is None:
		load_mb = 718
	if load_mb is None and load_gb is not None:
		load_mb = int(round(load_gb * 125))
	elif load_gb is None and load_mb is not None:
		load_gb = load_mb / 125.0
	miss_rate = kwargs.get('miss_rate', 1.48)
	coverage = kwargs.get('coverage', 21.3)
	hits_per_gb = kwargs.get('hits_per_gb', 0.9108)
	quality = kwargs.get('quality', 7865)
	fmt = '''
<tr>
	<td>{region:s}</td>
	<td style="padding-left:20px">{load_gb:.2f} Gbit/s</td>
	<td style="padding-left:5px; text-align:left">=</td>
	<td style="padding-left:5px; text-align:right">{load_mb:d} MB/s</td>
	<td style="padding-right:20px">{miss_rate:.2f} %</td>
	<td style="padding-right:20px">{coverage:.2f}</td>
	<td style="padding-right:5px">{hits_per_gb:.4f}</td>
	<td style="padding-right:10px">{quality:d}</td>
</tr>'''
	text = fmt.format(
		region=region, load_gb=load_gb, load_mb=load_mb, miss_rate=miss_rate, coverage=coverage,
		hits_per_gb=hits_per_gb, quality=quality
	)
	return text


def _create_client_text(**kwargs):
	cid = kwargs.get('id', '12345')
	name = kwargs.get('name', 'flandre')
	online = kwargs.get('online', True)
	online_color = 'green' if online else 'red'
	online_str = 'Online' if online else 'Offline'
	created = kwargs.get('created', '2018-01-01')
	n = now()
	last_seen = kwargs.get('last_seen', 'Today, ' + str(n.hour) + ':' + str(n.minute))
	files = kwargs.get('files', 60432)
	ip = kwargs.get('ip', '10.0.0.1')
	port = kwargs.get('port', 8888)
	version = kwargs.get('version', '1.4.2 Stable')
	speed = kwargs.get('speed', 820)
	trust = kwargs.get('trust', 988)
	trust_color = 'green' if trust >= 0 else 'red'
	quality = kwargs.get('quality', 8274)
	hitrate = kwargs.get('hitrate', 1.2)
	hathrate = kwargs.get('hathrate', 2.0)
	country = kwargs.get('country', 'United States')
	fmt = '''
<tr>
<td><a href="https://e-fancomics.org/fancomicsathome.php?cid={id:s}&amp;act=settings">{name:s}</a></td>
<td>{id:s}</td>
<td style="font-weight:bold; color:{online_color:s}">{online:s}</td>
<td>{created:s}</td>
<td>{last_seen:s}</td>
<td>{files:,d}</td>'''
	if online:
		fmt += '''
<td style="text-align:left; padding-left:7px">{ip:s}</td>
<td>{port:d}</td>
<td>{version:s}</td>
<td>{speed:d} KB/s</td>
<td style="color:{trust_color:s}">{trust:+d}</td>
<td>{quality:d}</td>
<td>{hitrate:.1f} / min</td>
<td>{hathrate:.1f} / day</td>
<td>{country:s}</td></tr>'''
	else:
		fmt += '<td colspan="8" style="font-style:italic; text-align:left; padding-left:7px">Not available when offline</td></tr>'
	text = fmt.format(
		id=cid, name=name, online_color=online_color, online=online_str, created=created, last_seen=last_seen,
		files=files, ip=ip, port=port, version=version, speed=speed, trust_color=trust_color, trust=trust,
		quality=quality, hitrate=hitrate, hathrate=hathrate, country=country
	)
	return text


def _create_body_text(*clients, **kwargs):
	text = '''<div class="stuffbox">
<h1>Fancomics@Home Clients</h1>

<div>

<table style="margin:20px auto 0; text-align:right; font-size:12pt">
<tr>
	<th>F@H Region</th>
	<th colspan="3" style="padding-left:20px; text-align:center">Current Network Load</th>
	<th style="padding-left:10px">F@H Miss%</th>
	<th style="padding-left:10px">Coverage</th>
	<th style="padding-left:10px">Hits/GB</th>
	<th style="padding-left:10px">Quality</th>
</tr>'''
	regions = kwargs.get('regions', None)
	if regions is None or len(regions) < 1:
		regions = [{
				'region': 'Asia and Oceania',
				'load_gb': 4.12,
				'load_mb': 515,
				'miss_rate': 2.05,
				'coverage': 5.01,
				'hits_per_gb': 0.9108,
				'quality': 7445
			},
			{
				'region': 'Global',
				'load_gb': 5.75,
				'load_mb': 718,
				'miss_rate': 1.48,
				'coverage': 21.30,
				'hits_per_gb': 0.4130,
				'quality': 7865
			}
		]
	if len(clients) < 1:
		clients = [{}]
	for region in regions:
		text += _create_network_text(**region)

	text += '''
</table>

<div style="text-align:center; font-size:8pt; font-weight:bold; padding-top:5px">
	Current Network Load show how much raw bandwidth is currently used to serve images. This includes requests served by F@H as well as direct requests from the image servers.<br />
	F@H Miss% shows the percentage of requests for the region that would have gone to a F@H client if one was available, but where no client was ready to serve the request.<br />
	Coverage denotes the average number of times a static file range partition can be found within a given region, indicating the total available storage capacity.<br />
	Hits/GB shows the average number of hits per minute per gigabyte of allocated disk space for all online clients in the region for the last 24 hours.<br />
</div>

</div>
<div>
<p style="font-weight:bold; margin-top:10px">Your Active Clients</p>

<p style="padding:3px 10px">To add more clients, <a href="https://forums.e-fancomics.org/index.php?act=Msg&amp;CODE=4&amp;MID=6">PM Tenboro</a>. Make sure to read the requirements first to make sure that you qualify. Include the specs for the client in the message, and specify whether it is a home connection or a VPS/Dedicated. Each client requires its own unique public IPv4 address to run, and must either be reachable directly from the Internet, or have a port forwarded. These are technical requirements, and it is not possible to make any exceptions.</p>

<table class="hct">
<tr>
	<th>Client</th>
	<th>ID</th>
	<th>Status</th>
	<th>Created</th>
	<th>Last Seen</th>
	<th>Files Served</th>
	<th>Client IP</th>
	<th>Port</th>
	<th>Version</th>
	<th>Max Speed</th>
	<th>Trust</th>
	<th>Quality</th>
	<th>Hitrate</th>
	<th>Fathrate</th>
	<th>Country</th>
</tr>'''
	for client in clients:
		text += _create_client_text(**client)
	return text