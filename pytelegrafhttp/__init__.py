import argparse
import logging
import sys
from .pytelegrafhttp import start, stop, reload

_log = logging.getLogger('pytelegrafhttp')  # explicitly give package here so we don't end up getting '__main__'
_log.setLevel(logging.DEBUG)


def main():
	_setup_console_logger()

	# noinspection PyBroadException
	try:
		_parse_cli_and_run()
	except Exception:
		_log.exception("Problem during execution")
		sys.exit(1)
	sys.exit(0)


def _parse_cli_and_run():
	import sys
	print(sys.argv)
	parser = argparse.ArgumentParser(description="Get metrics by scraping HTTP sites.")

	# space at the end of metavar is not a typo; we need it so help output is prettier
	subparsers = parser.add_subparsers(description="Functionality to execute.", metavar=" SUBCOMMAND ", dest='cmd')
	subparsers.required = True

	# START
	start_desc = "Start execution of scraper."
	start_parser = subparsers.add_parser('start', help='Start the metrics scraper.', description=start_desc)
	""":type : argparse.ArgumentParser"""
	start_parser.add_argument('--config', help="Use the specified config file.", default='config.py')
	start_parser.set_defaults(func=lambda ns: start(ns.config))

	# STOP
	stop_desc = "Signals to a running metrics scraper to shut down, and waits for shut down to complete."
	stop_parser = subparsers.add_parser('stop', help='Stop a metrics scraper.', description=stop_desc)
	""":type : argparse.ArgumentParser"""
	stop_parser.add_argument('PID', type=int, help='PID of scraper to stop.')
	stop_parser.add_argument('--config', help="Use the specified config file.", default='config.py')
	stop_parser.set_defaults(func=lambda ns: stop(ns.pid, ns.config))

	# RELOAD
	rel_desc = "Signals to a running metrics scraper to reload its configuration, and waits for it to complete."
	rel_parser = subparsers.add_parser(
		'reload-config',
		help='Reload the config of a metrics scraper.',
		description=rel_desc
	)
	""":type : argparse.ArgumentParser"""
	rel_parser.add_argument('PID', type=int, help='PID of scraper to tell to reload.')
	rel_parser.add_argument('--config', help="Use the specified config file.", default='config.py')
	rel_parser.set_defaults(func=lambda ns: reload(ns.pid, ns.config))

	args = parser.parse_args()
	args.func(args)


class _ExactLevelFilter(object):
	"""
	Only allows log records through that are particular levels.
	"""

	def __init__(self, levels):
		"""
		Creates a new exact level filter.
		:type levels: ``list[int|str]``
		:param levels: The levels that should pass through the filter; all others are filtered out. Each item is either
		one of the predefined level names or an integer level.
		"""
		self._levels = set()
		for lev in levels:
			is_int = False
			try:
				lev = lev.upper()
			except AttributeError:
				is_int = True
			if not is_int:
				if lev == 'DEBUG':
					self._levels.add(logging.DEBUG)
				elif lev == 'INFO':
					self._levels.add(logging.INFO)
				elif lev == 'WARNING' or lev == 'WARN':
					self._levels.add(logging.WARNING)
				elif lev == 'ERROR':
					self._levels.add(logging.ERROR)
				elif lev == 'CRITICAL':
					self._levels.add(logging.CRITICAL)
				else:
					raise ValueError("bad level name in levels list: " + lev)
			else:
				self._levels.add(int(lev))

	def num_levels(self):
		"""
		Gets the number of levels that are allowed through the filter.
		:rtype: ``int``
		:return: The number of levels.
		"""
		return len(self._levels)

	def min_level(self):
		"""
		Gets the minimum level that is allowed through the filter.
		:rtype: ``int``
		:return: The minimum leel
		"""
		return min(self._levels)

	def filter(self, record):
		"""
		Check whether to include the given log record in the output.

		:type record: ``logging.LogRecord``
		:param record: The record to check.
		:rtype: ``int``
		:return: 0 indicates the log record should be discarded; non-zero indicates that the record should be
		logged.
		"""
		if record.levelno in self._levels:
			return 1
		else:
			return 0


def _setup_console_logger():
	stderr_handler = logging.StreamHandler(stream=sys.stderr)
	stderr_handler.setLevel(logging.WARNING)
	stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
	logging.getLogger().addHandler(stderr_handler)

	lev_filter = _ExactLevelFilter(['INFO'])
	stdout_handler = logging.StreamHandler(stream=sys.stdout)
	stdout_handler.setLevel(lev_filter.min_level())
	stdout_handler.setFormatter(logging.Formatter("%(message)s"))
	stdout_handler.addFilter(lev_filter)
	logging.getLogger().addHandler(stdout_handler)