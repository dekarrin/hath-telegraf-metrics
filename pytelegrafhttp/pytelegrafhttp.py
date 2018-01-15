"""
Main controls for starting/stopping the agent.
"""
import logging
import logging.handlers
import re
from .scrape import PageScraper
import os

# all new handlers should go in the module-level logger, so we get the package logger
_log = logging.getLogger('pytelegrafhttp')


def start(config_file: str='config.py'):
	conf = _config_from_path(config_file)
	out_log = conf.log_main_log_path
	err_log = conf.log_error_log_path
	max_num = int(conf.log_file_keep_count)
	size = _size_to_bytes(conf.log_file_max_size)
	_setup_file_loggers(out_log, err_log, size, max_num)

	os_log_modes = conf.log_os_logs
	if 'systemd' in os_log_modes:
		_setup_systemd_logger()

	_setup_traps()

	run_dir = conf.execution_dir

	scraper = PageScraper()





def stop(pid: int):
	pass


def reload(pid: int, config_file: str='config.py'):
	pass


class ConfigException(Exception):
	"""Raised when there is a problem with a value in the configuration."""

	def __init__(self, msg, key):
		"""
		:param msg: The detail message.
		:param key: The key in the config file that there was a problem with. Should be a string that uniquely
		identifies the key.
		"""
		self.key = key
		super(self).__init__(msg)


def _handle_signal(signal_name):
	_log.info(signal_name + " received; shutdown")
	sys.exit(0)


def _setup_traps():
	import signal
	import os
	signal.signal(signal.SIGTERM, lambda x, y: _handle_sigterm())
	if os.name != 'nt':
		# Windows does not allow these signals, but other systems do
		signal.signal(signal.SIGHUP, lambda x, y: _handle_sighup())
	else:
		# This handler will exist on windows, so don't show warnings
		# noinspection PyUnresolvedReferences
		signal.signal(signal.SIGBREAK, lambda x, y: _handle_signal("SIGBREAK"))


def _config_from_path(path):
	from importlib.machinery import SourceFileLoader
	# We are aware that load_module() has been deprecated,
	# but it's the only way to do this without bumping the required python version up to 3.5
	config = SourceFileLoader('config', path).load_module()
	return config


def _setup_file_loggers(out_log, err_log, size, max_num):
	main_file_handler = logging.handlers.RotatingFileHandler(filename=out_log, maxBytes=size, backupCount=max_num)
	main_file_handler.setFormatter(logging.Formatter(fmt="%(asctime)-22s: [%(levelname)-10s] %(message)s"))
	main_file_handler.setLevel(logging.DEBUG)
	_log.addHandler(main_file_handler)

	err_file_handler = logging.handlers.RotatingFileHandler(filename=err_log, maxBytes=size, backupCount=max_num)
	err_file_handler.setFormatter(logging.Formatter(fmt="%(asctime)-22s: [%(levelname)-10s] %(message)s"))
	err_file_handler.setLevel(logging.WARNING)
	_log.addHandler(err_file_handler)


def _size_to_bytes(size):
	"""
	Parse a string with a size into a number of bytes. I.e. parses "10m", "10MB", "10 M" and other variations into the
	number of bytes in ten megabytes. Floating-point numbers are rounded to the nearest byte.

	:type size: ``str``
	:param size: The size to parse, given as a string with byte unit. No byte unit is assumed to be in bytes. Scientific
	notation is not allowed; must be an integer or real number followed by a case-insensitive byte unit (e.g. as "k" or
	"KB" for kilobyte, "g" or "Gb" for gigabyte, or a similar convention). Positive/negative sign in front of number is
	allowed.
	:rtype: ``long``
	:return: The number of bytes represented by the given string.
	"""
	units = 'KMGTPEZY'  # note that position of letter is same as power - 1
	match = re.search(r'^\s*([-+]?\s*[0-9]*\.?[0-9]*)\s*([' + units + r']?\s*B?\s*S?)\s*', size, re.IGNORECASE)
	if match is None:
		raise ValueError("size string not in proper format 'number [kmgtpezy]': " + size)
	mem_size = float(re.sub(r'\s*', '', match.group(1)))
	unit = re.sub(r'\s*', '', match.group(2)).upper()
	unit = re.sub(r'[BS]$', '', unit)  # remove trailing units symbol
	if unit == '':
		unit_pow = 0
	else:
		unit_pow = units.find(unit) + 1
	byte_size = int(round(mem_size * (1024 ** unit_pow)))
	return byte_size


def _setup_systemd_logger():
	try:
		from systemd.journal import JournalHandler
	except ImportError:
		raise ConfigException("OS log for systemd not supported; module not installed", 'log_os_logs')
	_log.addHandler(JournalHandler())