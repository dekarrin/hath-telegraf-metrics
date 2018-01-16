"""
Contains utility classes.
"""

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