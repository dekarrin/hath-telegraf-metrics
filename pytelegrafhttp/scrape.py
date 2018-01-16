"""
Contains scraper class for system.
"""
from .clock import TickClock
from . import util
import base64
import re


class PageScraper(object):

	def __init__(self):
		self._running = True
		self._use_ssl = False
		self._host = None
		self._user = None
		self._pass_encodes = None
		self._password = None
		self._login_process = None
		self._endpoints = None
		self._logged_in = False
		super(self).__init__()

	def load_config(self, conf):
		host = conf.scraper_host
		user = conf.scraper_username
		passwd = conf.scraper_password
		ssl = conf.scraper_use_ssl
		login_process = conf.scraper_login_steps

		self._use_ssl = ssl
		self._host = host
		self._user = user
		self._password = base64.b85encode(passwd.encode('utf-8'))
		self._login_process = parse_config_login_steps(conf.scraper_login_steps, 'scraper_login_steps')
		self._endpoints = parse_config_endpoints(conf.scraper_endpoints, 'scraper_endpoints')
		self._logged_in = False

	def run_tick(self, clock: TickClock):
		if not self._logged_in:
			self.login()

	def login(self):
		pass

	@property
	def running(self):
		return self._running

	@property
	def username(self):
		return self._user

	@property
	def host(self):
		return self._host

	@property
	def is_using_ssl(self):
		return self._use_ssl


def parse_config_login_steps(steps, key_path):
	parsed_steps = []
	idx = 0
	for step in steps:
		key = key_path + "[" + str(idx) + "]"
		try:
			step_type = step[0]
			step_data = step[1]
		except IndexError:
			raise util.ConfigException("login step must be a sequence(str, {{}}) that contains type and data.", key)

		parsed_step = {'type': step_type}

		key = key + '[1]'
		if step_type == 'attempt':
			try:
				parsed_step['endpoint'] = str(step_data['endpoint'])
			except KeyError:
				raise util.ConfigException("'attempt' login step data must include 'endpoint'", key)
		elif step_type == 'resp-extract':
			try:
				t = str(step_data['type'])
			except KeyError:
				raise util.ConfigException("'resp-extract' login step data must include 'type'", key)

			parsed_step['extract-type'] = t

			if t == 'form-vars':
				pass  # no additional data
			else:
				raise util.ConfigException("unknown subtype for 'resp-extract' login step: '" + t + "'", key + "['type']")
		elif step_type == 'submit-form':
			pass  # no additional data
		elif step_type == 'verify':
			try:
				parsed_step['pattern'] = re.compile(str(step_data['pattern']))
			except KeyError:
				raise util.ConfigException("'verify' login step data must include 'pattern'", key)
			except re.error as e:
				raise util.ConfigException("'verify' login step does not contain compilable regex; " + str(e), key + "['pattern']")
		else:
			raise util.ConfigException("unknown type for login step: '" + step_type + "'", key + '[0]')
		parsed_steps.append(parsed_step)
		idx += 1
	return parsed_steps


def parse_config_endpoints(endpoints, key_path):
	parsed_endpoints = []
	idx = 0
	for ep_data in endpoints:
		key = key_path + "[" + str(idx) + "]"
		parsed_ep = {}
		try:
			parsed_ep['endpoint'] = str(ep_data['endpoint'])
		except KeyError:
			raise util.ConfigException("endpoint data must contain 'endpoint' key", key)

		try:
			parsed_ep['verify-pattern'] = re.compile(ep_data['verify-pattern'])
		except KeyError:
			raise util.ConfigException("endpoint data must contain 'verify-pattern'", key)
		except re.error as e:
			raise util.ConfigException("endpoint verify pattern regex is not compilable; " + str(e), key + "['verify-pattern']")

		try:
			ep_metrics = ep_data['metrics']
		except KeyError:
			raise util.ConfigException("endpoint data must contain 'metrics' list", key)

		parsed_ep['metrics'] = parse_config_metrics(ep_metrics, key + "['metrics']")
		parsed_endpoints.append(parsed_ep)
		idx += 1
	return parsed_endpoints


def parse_config_metric_values(values, key_path):
	idx = 0
	parsed_values = []
	for v in values:
		parsed_v = {}
		key = key_path + '[' + str(idx) + ']'

		try:
			parsed_v['name'] = str(v['name'])
		except KeyError:
			raise util.ConfigException("metric value must contain 'name'", key)

		try:
			parsed_v['type'] = v['type']
		except KeyError:
			raise util.ConfigException("metric value must contain 'type'", key)
		if type(parsed_v['type']) is not type and type(parsed_v['type']) is not function:
			raise util.ConfigException("metric value conversion type be a type or a lambda", key + "['type']")

		try:
			parsed_v['capture'] = int(v['capture'])
		except KeyError:
			raise util.ConfigException("metric value must contain 'capture'", key)
		except ValueError:
			raise util.ConfigException("metric value capture must be an int", key + "['capture']")
		idx += 1
		parsed_values.append(parsed_v)
	return parsed_values


def parse_config_metrics(metrics, key_path):
	idx = 0
	parsed_metrics = []
	for m in metrics:
		parsed_met = {}
		key = key_path + '[' + str(idx) + ']'
		try:
			parsed_met['dest'] = str(m['dest'])
		except KeyError:
			raise util.ConfigException("endpoint metric must contain 'dest' key", key)

		try:
			parsed_met['name'] = str(m['name'])
		except KeyError:
			raise util.ConfigException("endpoint metric must contain 'dest' key", key)

		try:
			parsed_met['regex'] = re.compile(''.join(m['regex']))
		except KeyError:
			raise util.ConfigException("endpoint metric must contain 'regex' list", key)
		except re.error as e:
			raise util.ConfigException("metric regex not compilable; " + str(e), key + "['regex']")

		try:
			ep_metric_values = m['values']
		except KeyError:
			raise util.ConfigException("endpoint metric must contain 'values' list", key)

		try:
			ep_metric_tags = m['tags']
		except KeyError:
			raise util.ConfigException("endpoint metric must contain 'tags' map", key)

		parsed_met['values'] = parse_config_metric_values(ep_metric_values, key + "['values']")
		parsed_met['tags'] = parse_config_metric_tags(ep_metric_tags, key + "['tags']")
		parsed_metrics.append(parsed_met)
		idx += 1
	return parsed_metrics


def parse_config_metric_tags(tags, key_path):
	parsed_tags = {}
	for name in tags:
		t_name = str(name)
		key = key_path + "['" + t_name + "']"
		try:
			t_value = str(tags[t_name])
		except KeyError:
			raise util.ConfigException("metric tags must have str-type name", key)
		if re.match(r'CAPTURE-\d+', t_value) is not None:
			cap, cap_group = t_value.split('-')
			parsed_tags[t_name] = {
				'type': 'capture',
				'value': int(cap_group)
			}
		else:
			parsed_tags[t_name] = {
				'type': 'const',
				'value': t_value
			}
	return parsed_tags
