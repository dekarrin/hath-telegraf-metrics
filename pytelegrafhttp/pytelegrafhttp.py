"""
Main controls for starting/stopping the agent.
"""
import logging
import logging.handlers
import re
import sys
from . import scrape, daemon, clock as tickclock, util
import os

# all new handlers should go in the module-level logger, so we get the package logger
_log = logging.getLogger('pytelegrafhttp')


def start(config_file: str='config.py', no_cookies=False, disable_antiflood=False):
	os_logs = []
	conf = None
	main_log = None
	err_log = None
	secs_per_tick = 0.0
	daemon_com = daemon.DaemonCommunicator()
	scraper = scrape.PageScraper(antiflood=not disable_antiflood)
	clock = tickclock.TickClock()

	def load_config():
		nonlocal conf, os_logs, main_log, err_log, secs_per_tick, last_good_tick
		conf = _config_from_path(config_file)
		main_log = conf.log_main_log_path
		err_log = conf.log_error_log_path
		max_num = int(conf.log_file_keep_count)
		size = _size_to_bytes(conf.log_file_max_size)
		main_log, err_log = _setup_file_loggers(main_log, err_log, size, max_num)
		_log.addHandler(main_log)
		_log.addHandler(err_log)

		os_log_modes = conf.log_os_logs
		os_logs = []
		if 'systemd' in os_log_modes:
			os_log = _setup_systemd_logger()
			os_logs.append(os_log)
			_log.addHandler(os_log)

		secs_per_tick = int(conf.time_collection_interval)
		daemon_com.load_config(conf)
		scraper.load_config(conf)
		last_good_tick = clock.start(secs_per_tick).tick  # must be here because this function is called via signal

	def reload_scraper_config():
		nonlocal conf, os_logs, main_log, err_log, secs_per_tick, last_good_tick
		_log.info("Received SIGHUP; reloading config")
		_log.removeHandler(err_log)
		_log.removeHandler(main_log)
		for ol in os_logs:
			_log.removeHandler(ol)
		conf = _config_from_path(config_file)
		clock.stop()
		clock.reset()

		load_failed = False
		# noinspection PyBroadException
		try:
			load_config()
		except Exception:
			_log.exception("could not reload log; terminate now")
			load_failed = True
		daemon_com.signal_reload_completed()
		if load_failed:
			raise SystemExit()

	load_config()
	daemon_com.signal_started()
	_setup_traps(reload_scraper_config)

	# main loop
	try:
		scraper.setup(no_cookies)
		last_good_tick = clock.stop().reset().start(secs_per_tick).tick
		while scraper.running:
			# noinspection PyBroadException
			try:
				scraper.run_tick(clock)
				last_good_tick = clock.tick
			except scrape.FatalError as e:
				raise e
			except Exception:
				_log.exception("Problem in tick " + str(clock.tick))
				_log.error("Last good tick: " + str(last_good_tick))
			if scraper.running:
				clock.advance()
		_log.info("Scraper is no longer running.")
	except scrape.StateError:
		_log.exception("Bad state of scraper; cannot continue")
	except scrape.LoginError:
		_log.exception("Login to server failed; cannot continue")
	except scrape.BotKickedError:
		_log.exception("Scraper was kicked for performing in suspicious manner; cannot continue")
	except KeyboardInterrupt:
		_log.info("Interrupted by user")
	except SystemExit:
		_log.info("System exited")
	finally:
		scraper.cleanup()
		daemon_com.signal_terminated()
		_log.info("Clean shutdown")

	_log.info("System exit")


def stop(pid: int, config_file: str='config.py'):
	import signal
	conf = _config_from_path(config_file)
	daemon_com = daemon.DaemonCommunicator()
	daemon_com.load_config(conf)
	os.kill(pid, signal.SIGTERM)
	daemon_com.wait_for_termination(pid)


def reload(pid: int, config_file: str='config.py'):
	import signal
	conf = _config_from_path(config_file)
	daemon_com = daemon.DaemonCommunicator()
	daemon_com.load_config(conf)
	daemon_com.signal_reload_start(pid)
	os.kill(pid, signal.SIGHUP)
	daemon_com.wait_for_reload(pid)


def _handle_signal(signal_name):
	_log.info(signal_name + " received; shutdown")
	sys.exit(0)


def _setup_traps(sighup_closure):
	import signal
	import os
	signal.signal(signal.SIGTERM, lambda x, y: _handle_signal("SIGTERM"))
	if os.name != 'nt':
		# Windows does not allow these signals, but other systems do
		signal.signal(signal.SIGHUP, lambda x, y: sighup_closure)
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

	err_file_handler = logging.handlers.RotatingFileHandler(filename=err_log, maxBytes=size, backupCount=max_num)
	err_file_handler.setFormatter(logging.Formatter(fmt="%(asctime)-22s: [%(levelname)-10s] %(message)s"))
	err_file_handler.setLevel(logging.WARNING)
	return main_file_handler, err_file_handler


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
	if match is None or match.group(1) == '':
		raise ValueError("size string not in proper format 'number [kmgtpezy]': " + size)
	mem_size = float(re.sub(r'\s*', '', match.group(1)))
	unit = re.sub(r'\s*', '', match.group(2)).upper()
	unit = re.sub(r'B?S?$', '', unit)  # remove trailing units symbol
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
		raise util.ConfigException("OS log for systemd not supported; module not installed", 'log_os_logs')
	return JournalHandler()
