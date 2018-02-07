"""
Contains utility classes.
"""
import re


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


class ConfigException(Exception):
	"""Raised when there is a problem with a value in the configuration."""

	def __init__(self, msg, key):
		"""
		:param msg: The detail message.
		:param key: The key in the config file that there was a problem with. Should be a string that uniquely
		identifies the key.
		"""
		self.key = key
		super().__init__(msg)


# used for checking whether client is online based on last seen time.
def check_online(last_seen_str, max_minutes):
	from dateparser import parse
	from datetime import datetime, timezone, timedelta
	now = datetime.utcnow().replace(tzinfo=timezone.utc)
	last_seen = parse(last_seen_str, languages=['en'], settings={'TIMEZONE': 'UTC', 'RETURN_AS_TIMEZONE_AWARE': True})
	max_time = timedelta(minutes=max_minutes)
	return now - last_seen <= max_time


def get_config_regex(conf, var_name):
	"""
	Gets a config value as a regex pattern. Must be given as a string in the config file.

	:param conf: The config module to read.
	:param var_name: The name of the config variable.
	:rtype: re.__Regex
	:return: The config value.
	"""
	var_val = get_config_str(conf, var_name)
	try:
		var_val = re.compile(var_val, re.DOTALL)
	except re.error as e:
		raise ConfigException("Regex not valid: '" + str(var_val) + "': " + str(e), var_name)
	return var_val


def get_config_int(conf, var_name):
	"""
	Gets a config value as an integer value.

	:param conf: The config module to read.
	:param var_name: The name of the config variable.
	:rtype: int
	:return: The config value.
	"""
	try:
		var_val = getattr(conf, var_name)
	except AttributeError:
		raise ConfigException("Missing config definition", var_name)
	try:
		var_val = int(var_val)
	except ValueError:
		raise ConfigException("Not an int: " + str(var_val), var_name)
	return var_val


def get_config_float(conf, var_name):
	"""
	Gets a config value as a floating-point precision value.

	:param conf: The config module to read.
	:param var_name: The name of the config variable.
	:rtype: float
	:return: The config value.
	"""
	try:
		var_val = getattr(conf, var_name)
	except AttributeError:
		raise ConfigException("Missing config definition", var_name)
	try:
		var_val = float(var_val)
	except ValueError:
		raise ConfigException("Not a float: " + str(var_val), var_name)
	return var_val


def get_config_bool(conf, var_name):
	"""
	Gets a config value as a boolean value.

	:param conf: The config module to read.
	:param var_name: The name of the config variable.
	:rtype: bool
	:return: The config value.
	"""
	try:
		var_val = getattr(conf, var_name)
	except AttributeError:
		raise ConfigException("Missing config definition", var_name)
	try:
		var_val = bool(var_val)
	except ValueError:
		raise ConfigException("Not a bool: " + str(var_val), var_name)
	return var_val


def get_config_str(conf, var_name):
	"""
	Gets a config value as a string.

	:param conf: The config module to read.
	:param var_name: The name of the config variable.
	:rtype: str
	:return: The config value.
	"""
	try:
		var_val = getattr(conf, var_name)
	except AttributeError:
		raise ConfigException("Missing config definition", var_name)
	try:
		var_val = str(var_val)
	except ValueError:
		raise ConfigException("Value not convertable to str", var_name)
	return var_val
