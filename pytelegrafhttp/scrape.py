"""
Contains scraper class for system.
"""
from .clock import TickClock
from . import util, http
import base64
import re
import time
import random
import urllib.parse
import logging
from .clock import now_ts
import pprint
import pickle
import html
from telegraf.client import TelegrafClient


_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class FatalError(Exception):
	"""
	Raised for actions that the scraper cannot recover from. If one of these is raised, the running state is set to
	false and the scraper should not be used anymore.
	"""

	def __init__(self, msg):
		super().__init__(msg)


class StateError(FatalError):
	"""
	Raised when the scraper is not in the appropriate state to perform the requested action.
	"""
	def __init__(self, msg):
		"""
		Creates a new StateError.

		:param msg: The messages.
		"""
		super().__init__(msg)


class LoginError(FatalError):
	"""
	Raised when login could not be completed.
	"""
	def __init__(self, msg):
		"""
		Creates a new LoginError.

		:param msg: The messages.
		"""
		super().__init__(msg)


class BotKickedError(FatalError):
	"""
	Raised when client is kicked for misbehaving as a bot.
	"""
	def __init__(self, msg):
		"""
		Creates a new BotKickedError.

		:param msg: The message.
		"""
		super().__init__(msg)


class AuthError(Exception):
	"""
	Raised when a current good session appears to have expired.
	"""
	def __init__(self, msg):
		"""
		Creates a new AuthError.

		:param msg: The message.
		"""
		super().__init__(msg)


class VerificationError(Exception):
	"""
	Raise when a page did not match the expected content.
	"""

	def __init__(self, msg, content):
		"""
		Creates a new VerificationError.

		:param msg: The messages.
		:param content: The content that did not match.
		"""
		self.content = content
		super().__init__(msg)


class PageScraper(object):

	def __init__(self, antiflood):
		self._antiflood = antiflood
		self._client = http.HttpAgent('localhost', request_payload='form', response_payload='text')
		self._running = False
		self._agent = False
		self._user = None
		self._password = None
		self._login_steps = None
		self._endpoints = None
		self._logged_in = False
		self._login_response = None
		self._login_form = None
		self._cookies_file = None
		self._state_file = None
		self._save_frequency = 0
		self._logged_out_pattern = None
		self._bot_kicked_pattern = None
		self._telegraf_clients = {}
		super().__init__()

	def load_config(self, conf):
		# try to load config before setting values, so a later one being invalid does not leave us in a
		# partially-updated state
		logged_out_pattern = util.get_config_regex(conf, 'scraper_logged_out_pattern')
		bot_kicked_pattern = util.get_config_regex(conf, 'scraper_bot_kicked_pattern')
		ssl = util.get_config_bool(conf, 'scraper_use_ssl')
		host = util.get_config_str(conf, 'scraper_host')
		user = util.get_config_str(conf, 'scraper_username')
		passwd = util.get_config_str(conf, 'scraper_password')
		login_steps = parse_config_login_steps(conf.scraper_login_steps, 'scraper_login_steps')
		endpoints = parse_config_endpoints(conf.scraper_endpoints, 'scraper_endpoints')
		tele_confs = parse_config_telegraf_clients(conf.scraper_telegraf_destinations, 'scraper_telegraf_destinations')
		cookies_file = util.get_config_str(conf, 'env_cookies_file')
		state_file = util.get_config_str(conf, 'env_state_file')
		save_freq = util.get_config_int(conf, 'time_save_frequency')

		self._logged_out_pattern = logged_out_pattern
		self._bot_kicked_pattern = bot_kicked_pattern
		self._client.ssl = ssl
		self._client.host = host
		self._user = user
		self._password = base64.b85encode(passwd.encode('utf-8'))
		self._login_steps = login_steps
		self._endpoints = endpoints
		self._logged_in = False
		self._cookies_file = cookies_file
		self._state_file = state_file
		self._save_frequency = save_freq
		self._telegraf_clients = {}
		for tele in tele_confs:
			client_conf = tele_confs[tele]
			self._telegraf_clients[tele] = TelegrafClient(port=client_conf['port'], tags=client_conf['tags'])
		self._client.start_new_session()

	def setup(self, no_cookies=False):
		"""
		Restore any necessary state.
		"""
		if not no_cookies:
			loaded_cookies = self._load_state()
		else:
			loaded_cookies = False

		if not loaded_cookies or not self._logged_in:
			_log.info("Attempting initial login...")
			self._login()
			_log.info("Login successful")
		self._running = True

	def run_tick(self, clock):
		"""
		:type clock: TickClock
		:param clock: Current tick.
		"""
		if not self._running:
			raise StateError("Not currently running; call setup() first")
		if not self._logged_in:
			_log.warning("Not logged in; attempting login...")
			self._login()
			_log.info("Login successful")
			return
		if clock.tick % self._save_frequency == 0 and clock.tick != 0:
			self._save_state()

		for endpoint_data in self._endpoints:
			try:
				self._scrape_endpoint(endpoint_data)
			except VerificationError as e:
				if self._bot_kicked_pattern.search(e.content) is not None:
					raise BotKickedError("automated client was kicked/banned from the server: " + e.content)
				elif self._logged_out_pattern.search(e.content) is not None:
					self._logged_in = False
					raise AuthError("login is no longer valid")

	def cleanup(self):
		"""
		Prepare for shutdown.
		"""
		if self._running:
			self._save_state()

	def antiflood_wait(self):
		"""For multi-request operations, make sure we don't overload the server."""
		# Numbers in this range are random, however it does seem that 2.5 seconds is a reasonable minimum for avoiding
		# abuse of the system.
		if self._antiflood:
			secs = random.uniform(2.5, 6.5)
			time.sleep(secs)

	def _scrape_endpoint(self, endpoint_data):
		endpoint = endpoint_data['endpoint']
		verify_pattern = endpoint_data['verify-pattern']
		metrics = endpoint_data['metrics']

		ts = now_ts(ms=True) * 1000000  # influx db has nano-second precision

		status, endpoint_text = self._client.request('GET', endpoint)
		if verify_pattern.search(endpoint_text) is None:
			raise VerificationError("endpoint did not match expected content", endpoint_text)
		idx = 0
		bursts = []
		for m in metrics:
			dest_channel = m['dest']
			metric_name = m['name']
			pattern = m['regex']
			metric_value_definitions = m['values']
			metric_tag_definitions = m['tags']

			if pattern.search(endpoint_text) is None:
				warning_text = "endpoint '" + endpoint + "', metric " + str(idx) + " (" + metric_name + ")"
				warning_text += " could not be found. Skipping for this unit of time"
				_log.warning(warning_text)
				continue

			# find all matches
			matchers = pattern.finditer(endpoint_text)
			for matcher in matchers:
				# build the values from the matched items
				metric_values = {}
				for value_def in metric_value_definitions:
					value_name = value_def['name']
					value_type = value_def['type']
					value_conv = value_def['conversion']
					if value_type == 'capture':
						value_group = value_def['capture']
						metric_values[value_name] = value_type(matcher.group(value_group))
					elif value_type == 'custom':
						metric_values[value_name] = value_type(matcher)
					elif value_type == 'const':
						metric_values[value_name] = value_conv
					else:
						# should be caught during config parsing, but double-check
						raise ValueError("Bad metric value definition type: " + repr(value_type))

				metric_tags = {}
				for tag_name in metric_tag_definitions:
					tag_def = metric_tag_definitions[tag_name]
					tag_type = tag_def['type']
					if tag_type == 'capture':
						tag_value = matcher.group(tag_def['value'])
					elif tag_type == 'const':
						tag_value = tag_def['value']
					else:
						# should be caught during config parsing, but double-check
						raise ValueError("Bad metric tag definition type: " + repr(tag_type))
					metric_tags[tag_name] = tag_value

				bursts.append((dest_channel, {
					'metric': metric_name,
					'values': metric_values,
					'tags': metric_tags
				}))
			idx += 1

		_log.info("Got metrics for " + endpoint + "; sending...")
		for b in bursts:
			self._send_metric_burst(b[0], ts, b[1]['metric'], b[1]['values'], b[1]['tags'])

	def _send_metric_burst(self, channel, timestamp, metric, values, tags):
		if channel not in self._telegraf_clients:
			_log.warning("No configured telegraf client for channel '" + channel + "'")
			return
		client = self._telegraf_clients[channel]
		client.metric(metric, values, tags=tags, timestamp=timestamp)

	def _login(self):
		self._login_response = None
		self._login_form = None
		try:
			for step in self._login_steps:
				if step['type'] == 'attempt':
					self._login_attempt_get(step['endpoint'])
					self.antiflood_wait()
				elif step['type'] == 'resp-extract':
					if step['extract-type'] == 'form-vars':
						self._login_extract_response_form(step['inject'])
					else:
						raise ValueError("Bad login step extract-type: " + step['extract-type'])
				elif step['type'] == 'submit-form':
					self._login_submit_form()
					self.antiflood_wait()
				elif step['type'] == 'verify':
					if not self._login_verify_response(step['pattern']):
						self._running = False
						raise LoginError("Verification of login failed!")
					else:
						self._logged_in = True
				elif step['type'] == 'bounce-transfer':
					self._login_bounce_transfer(step['pattern'])
					self.antiflood_wait()
				else:
					raise ValueError("Bad login step type: " + step['type'])
		finally:
			self._login_response = None
			self._login_form = None

	def _login_bounce_transfer(self, pattern):
		m = pattern.search(self._login_response)
		if m is None:
			raise LoginError("Could not bounce from login response; regex failed")
		next_link = self._parse_link(m.group(1))

		uri = next_link['uri']
		host = next_link['host']
		params = next_link['query']

		status, self._login_response = self._client.request('GET', uri, host=host, query=params)

	def _login_verify_response(self, pattern):
		return pattern.search(self._login_response) is not None

	def _login_attempt_get(self, endpoint):
		status, self._login_response = self._client.request('GET', endpoint)

	def _login_submit_form(self):
		if self._login_form['method'] == 'GET':
			params = self._login_form['variables']
			payload = None
		else:
			params = None
			payload = self._login_form['variables']
		meth = self._login_form['method']
		action = self._login_form['action']
		uri = action['uri']
		host = action['host']
		if action['query'] is not None:
			if params is not None:
				params = {**params, **action['query']}
			else:
				params = action['query']

		status, self._login_response = self._client.request(meth, uri, host=host, query=params, payload=payload)

	def _login_extract_response_form(self, injections):
		# first, find the form element
		m = re.search(r'<form.*?</form>', self._login_response, re.DOTALL)
		if not m:
			raise LoginError("Could not extract form response; regex failed")
		form_text = m.group(0)
		form_open_tag = re.search(r'<form [^>]+>', form_text, re.DOTALL).group(0)
		form_action = re.search(r' action="([^"]+)"', form_open_tag, re.DOTALL).group(1)

		form_action = self._parse_link(form_action)

		form_method_m = re.search(r' method="([^"]+)"', form_open_tag, re.DOTALL)
		if form_method_m:
			form_method = form_method_m.group(1).upper()
		else:
			form_method = 'GET'

		# only input elements for now
		inputs = re.findall(r'<input [^>]+>', form_text, re.DOTALL)
		form_variables = {}
		for input_element in inputs:
			input_name = re.search(r' name="([^"]+)"', input_element, re.DOTALL).group(1)
			input_value_m = re.search(r' value="([^"]+)"', input_element, re.DOTALL)
			if input_value_m:
				input_value = input_value_m.group(1)
			else:
				input_value = ''
			if input_name in injections:
				var_name = injections[input_name]
				if var_name == 'username':
					input_value = self._user
				elif var_name == 'password':
					input_value = base64.b85decode(self._password).decode('utf-8')
				else:
					raise LoginError("Bad variable name in form injections")
			form_variables[input_name] = input_value

		self._login_form = {
			'action': form_action,
			'method': form_method,
			'variables': form_variables
		}

	def _parse_link(self, link):
		"""
		:rtype: dict
		"""
		link = html.unescape(link)
		components = {
			'host': None,
			'uri': None,
			'query': None
		}
		res = urllib.parse.urlparse(link)

		if res.netloc is not '' and res.netloc != self._client.host:
			components['host'] = res.netloc

		components['uri'] = res.path

		if res.query is not '':
			components['query'] = urllib.parse.parse_qs(res.query, keep_blank_values=True)

		return components

	def _save_state(self):
		self._client.save_cookies(self._cookies_file)
		_log.info("Wrote cookies to '" + self._cookies_file + "'")
		state = {'logged_in': self._logged_in}
		with open(self._state_file, 'wb') as f:
			pickle.dump(state, f)
			_log.info("Wrote state to '" + self._state_file + "'")

	def _load_state(self):
		loaded_cookies = False
		try:
			self._client.load_cookies(self._cookies_file)
			loaded_cookies = True
			_log.info("Read cookies from '" + self._cookies_file + "'")
		except FileNotFoundError:
			_log.debug("Cookies file not found at '" + self._cookies_file + "'; skipping")

		try:
			with open(self._state_file, 'rb') as f:
				state = pickle.load(f)
			_log.info("Read state from '" + self._state_file + "'")
			self._logged_in = state['logged_in']
		except FileNotFoundError:
			_log.debug("State file not found at '" + self._state_file + "'; skipping")

		return loaded_cookies

	@property
	def running(self):
		return self._running

	@property
	def username(self):
		return self._user


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
				parsed_step['inject'] = {}
				if 'inject' in step_data:
					for name in step_data['inject']:
						i_name = str(name)
						i_value = str(step_data['inject'][i_name])
						if i_value != 'username' and i_value != 'password':
							full_key = key + "['inject']['" + i_name + "']"
							raise util.ConfigException('login step injection vars: not a valid var name: ' + i_value, full_key)
						parsed_step['inject'][i_name] = i_value
			else:
				raise util.ConfigException("unknown subtype for 'resp-extract' login step: '" + t + "'", key + "['type']")
		elif step_type == 'bounce-transfer':
			try:
				parsed_step['pattern'] = re.compile(str(step_data['pattern']), re.DOTALL)
			except KeyError:
				raise util.ConfigException("'bounce-transfer' login step data must include 'pattern'", key)
			except re.error as e:
				msg = "'buonce-transfer' login step does not contain compilable regex; " + str(e)
				raise util.ConfigException(msg, key + "['pattern']")

		elif step_type == 'submit-form':
			pass  # no additional data
		elif step_type == 'verify':
			try:
				parsed_step['pattern'] = re.compile(str(step_data['pattern']), re.DOTALL)
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
			parsed_ep['verify-pattern'] = re.compile(ep_data['verify-pattern'], re.DOTALL)
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
			v_type = v['type'].upper()
		except KeyError:
			raise util.ConfigException("metric value must contain 'type'", key)
		except AttributeError:
			raise util.ConfigException("metric value must be of str type", key + "['type']")

		try:
			v_conv = v['conversion']
		except KeyError:
			raise util.ConfigException("metric value must contain 'conversion'", key)

		if re.match(r'CAPTURE-\d+', v_type) is not None:
			cap, cap_group = v_type.split('-')
			parsed_v['capture'] = int(cap_group)
			parsed_v['type'] = 'capture'
		elif v_type == 'VALUE':
			parsed_v['type'] = 'const'
		elif v_type == 'CUSTOM':
			parsed_v['type'] = 'custom'
		else:
			msg = "metric value 'type' must be one of 'CUSTOM', 'VALUE', or 'CAPTURE-*' formats"
			raise util.ConfigException(msg, key + "['type']")

		if parsed_v['type'] != 'const' and type(v_conv) is not type and not callable(v_conv):
			msg = "metric value conversion be a type or a callable when type is not 'VALUE'"
			raise util.ConfigException(msg, key + "['conversion']")
		parsed_v['conversion'] = v_conv

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
			parsed_met['regex'] = re.compile(''.join(m['regex']), re.DOTALL)
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
			t_value = str(tags[t_name]).upper()
		except KeyError:
			raise util.ConfigException("metric tag keys must be str() type.", key)
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


def parse_config_telegraf_clients(clients, key_path):
	parsed_clients = {}
	for name in clients:
		parsed_name = str(name)
		key = key_path + "['" + parsed_name + "']"
		try:
			cl_value = clients[parsed_name]
		except KeyError:
			raise util.ConfigException("telegraf destination must be str() type", key)

		try:
			c_port = int(cl_value['port'])
		except KeyError:
			raise util.ConfigException("telegraf destination must contain 'port' key", key)
		except ValueError:
			raise util.ConfigException("telegraf destination port not a valid int", key)

		try:
			tags = dict(cl_value['global-tags'])
		except KeyError:
			raise util.ConfigException("telegraf destination must contain 'global-tags' key", key)
		except ValueError:
			raise util.ConfigException("telegraf destination global tags not a valid dict", key)

		parsed_clients[parsed_name] = {'port': c_port, 'tags': tags}
	return parsed_clients
