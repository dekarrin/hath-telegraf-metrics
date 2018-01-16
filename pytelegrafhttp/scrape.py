"""
Contains scraper class for system.
"""
from .clock import TickClock


class PageScraper(object):

	def __init__(self):
		self._running = True
		super(self).__init__()

	def new_session(self):
		pass

	def run_tick(self, clock: TickClock):
		pass

	@property
	def running(self):
		return self._running
