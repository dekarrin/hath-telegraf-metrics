"""
For communication between different daemons.
"""
import os
import time


class DaemonCommunicator(object):
	"""For communication between the main process and its controllers."""

	def __init__(self):
		self._daemon_dir = None
		self._owner_pid = os.getpid()

	def load_config(self, conf):
		self._daemon_dir = conf.env_daemon_files_dir
		self.clear_signals()

	def clear_signals(self):
		fn = self._get_filename_for('running')
		if os.path.isfile(fn):
			os.remove(fn)

	def signal_started(self):
		fn = self._get_filename_for('running')
		if os.path.isfile(fn):
			raise ValueError("out of order signaling; pid lockfile already exists")
		else:
			_touch(fn)

	def signal_terminated(self):
		fn = self._get_filename_for('running')
		if not os.path.isfile(fn):
			raise ValueError("out of order signaling; pid lockfile does not exist")
		else:
			os.remove(fn)

	def signal_reload_completed(self):
		fn = self._get_filename_for('reload')
		if not os.path.isfile(fn):
			raise ValueError("out of order signaling; pid reload lockfile does not exist")
		else:
			os.remove(fn)

	def signal_reload_start(self, pid):
		fn = self._get_filename_for('reload', pid=pid)
		if os.path.isfile(fn):
			raise ValueError("out of order signaling; pid reload lockfile already exists")
		else:
			_touch(fn)

	def wait_for_termination(self, pid, timeout=30):
		fn = self._get_filename_for('running', pid=pid)
		start = time.monotonic()
		while os.path.isfile(fn):
			time.sleep(0.1)
			if time.monotonic() - start > timeout:
				raise TimeoutError("timed out while waiting for main process to exit")

	def wait_for_reload(self, pid, timeout=30):
		fn = self._get_filename_for('reload', pid=pid)
		start = time.monotonic()
		while os.path.isfile(fn):
			time.sleep(0.1)
			if time.monotonic() - start > timeout:
				raise TimeoutError("timed out while waiting for main process to reload")

	def _get_filename_for(self, name, pid=None):
		if pid is None:
			pid = self._owner_pid
		return os.path.join(self._daemon_dir, str(pid) + '.' + name + '.lock')


def _touch(path):
	with open(path, 'a'):
		os.utime(path, None)
