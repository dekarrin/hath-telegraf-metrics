import sys
import threading
import datetime
import logging
import time


_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


# Uninterruptable code
def _no_interrupt(fun):
	"""
	Executes the given function in a context where it can't be interrupted by keyboard interupts.
	:type fun: ``() -> Any``
	:param fun: The function to run. If it returns something, that will be returned by _no_interrupt.
	:rtype: ``Any``
	:return: Whatever the result of executing the function is.
	"""

	def thread_func(r):
		# noinspection PyBroadException
		try:
			r[0] = fun()
		except BaseException:
			r[1] = sys.exc_info()
	result = [None, None]
	""":type: list"""
	th = threading.Thread(target=thread_func, args=(result,))
	th.start()
	th.join()
	if result[1] is not None:
		inf = result[1]
		raise inf[1].with_traceback(inf[2])
	return result[0]


class TickClock(object):
	"""
	Tracks time delta and ticks. Used for time-keeping.

	:type _prev_target_time: ``datetime.datetime``
	"""

	def __init__(self, tick=0, tick_speed=None, total_time=None, suspended=False, limiter_enabled=True):
		"""
		Creates a new TickClock. The current tick is set to the given number of ticks.
		:type tick: ``long``
		:param tick: Number of ticks to initialize time object with.
		:type tick_speed: ``float``
		:param tick_speed: Number of seconds per tick. Only give if the TickClock should be initialized with an active
		clock (generally not needed unless restoring from a serialized state).
		:type total_time: ``datetime.timedelta``
		:param total_time: Total time that has passed in this bot time. This includes time between calls to advance()
		when the bot time clock was not paused. If tick_speed is not set to a non-None value, this parameter has no
		effect.
		:type suspended: ``bool``
		:param suspended: Whether to start the bot time clock in the suspended state. If tick_speed is not set to a
		non-None value, this parameter has no effect.
		:type limiter_enabled: ``bool``
		:param limiter_enabled: Whether to enable the frame-limiting mechanism of the clock. If this is set to false,
		calls to advance will immediately advance the tick with no waiting, and no frame will ever be considered to be
		running slowly.
		"""
		self._tick = tick
		self._time = now()
		self._speed = None
		self._elapsed = None
		self._prev = None
		self._total = None
		self._is_slow = False
		self._clock_active = False
		self._clock_suspended = False
		self._limiter_enabled = limiter_enabled
		# tolerance for hitting time target is ten milliseconds. More off than that and it will be considered slow.
		self._target_tolerance = datetime.timedelta(seconds=0.01)
		self._prev_target_time = None
		if tick_speed is not None:
			# Then the clock has already been started.
			_no_interrupt(lambda: self._set_clock_props(datetime.timedelta(seconds=tick_speed), total_time))
			self._clock_active = True
			if suspended:
				self._clock_suspended = True

	def advance(self):
		"""
		Advances to the next tick. Thread will sleep until the time of the next tick arrives. This method should be
		called at the very end (but still within) the main loop of the associated bot. When this method returns, the
		properties of this TickClock will have been updated to reflect the new time information.

		:rtype: ``TickClock``
		:return This TickClock.
		"""
		if not self.is_running:
			raise ValueError("Clock must be running before calling advance()")
		if self._limiter_enabled:
			target_time = self._prev_target_time + self.speed
			self._prev_target_time = target_time
			sleep_time = max((target_time - now()).total_seconds(), 0.0)
			if sleep_time > 0:
				_log.debug("Sleep for %0.5f seconds", sleep_time)
				time.sleep(sleep_time)
		ts = now()
		_no_interrupt(lambda: self._increment_clock_props(ts))
		_log.debug("Clock advanced to tick " + str(self.tick))
		return self

	def suspend(self):
		"""
		Pause the clock so that time between now and when unpause() is next called does not count as slow execution for
		the bot.

		:rtype: ``TickClock``
		:return This TickClock.
		"""
		self._clock_suspended = True
		_log.debug("Clock suspended")
		return self

	def resume(self):
		"""
		Resumes the clock from a paused state and restarts the current tick.

		:rtype: ``TickClock``
		:return This TickClock.
		"""
		if self._speed is None:
			raise ValueError("clock not started, or was stopped after previous suspend")
		if not self._clock_suspended:
			return
		_no_interrupt(lambda: self._set_clock_props(self._speed, self._total))
		self._clock_suspended = False
		_log.debug("Clock resumed")
		return self

	def reset(self):
		""":rtype: TickClock"""
		self._tick = 0
		return self

	def start(self, tick_speed):
		"""
		Sets up the initial time that all future times are calculated relative to. This method should be called
		immediately before the associated bot enters its main loop.

		Once this method is called, the TickClock is put in the running state, and will remain running until stop_clock()
		is called.

		:type tick_speed: ``float``
		:param tick_speed: The amount of time each tick takes, in seconds.
		:rtype: ``TickClock``
		:return This TickClock.
		"""
		speed = datetime.timedelta(seconds=tick_speed)
		_no_interrupt(lambda: self._set_clock_props(speed))
		self._clock_active = True
		_log.debug("Clock started")
		return self

	def stop(self):
		"""
		Stops the bot time clock from running. After stop_clock() is called, start_clock() should be called before any
		future calls to advance().

		:rtype: ``TickClock``
		:return This TickClock.
		"""
		self._clock_active = False
		self._speed = None
		_log.debug("Clock stopped")
		return self

	def use_frame_limiter(self, value):
		"""
		Sets whether to use the frame limiter, which causes calls to advance() to block until the correct amount of time
		has passed.
		:type value: ``bool``
		:param value: Whether to use the frame-limiter.
		:rtype: ``TickClock``
		:return: This TickClock.
		"""
		self._limiter_enabled = value
		return self

	@property
	def tick(self):
		"""
		The current tick that the time is at. Time starts at 0 and increments with each call of advance().
		:rtype: ``long``
		:return: The current tick.
		"""
		return self._tick

	@property
	def time(self):
		"""
		The time of the current tick/update. This is the real-world system time as of the start of the current tick.
		:rtype: ``datetime.datetime``
		:return: The tick time.
		"""
		return self._time

	@property
	def elapsed(self):
		"""
		The amount of real-world time that has passed since the previous update.
		:rtype: ``datetime.timedelta``
		:return: The elapsed time.
		"""
		return self._elapsed

	@property
	def prev(self):
		"""
		The real-world time of the previous tick.
		:rtype: ``datetime.datetime``
		:return: The tick time of the previous tick.
		"""
		return self._prev

	@property
	def speed(self):
		"""
		The target amount of real-world time in between each update. Expressed in number of seconds per tick. Note that
		if a tick's operations take longer than this time to complete, they are not pre-empted.
		:rtype: ``datetime.timedelta``
		:return: The target tick time.
		"""
		return self._speed

	@property
	def total(self):
		"""
		The amount of real-world time that has passed since the bot time clock began running. Does not include time
		that the TickClock existed as a JSON object, if any such time is given.
		:rtype: ``datetime.timedelta``
		:return: The total amount of real-world time that has passed since bot time started.
		"""
		return self._total

	@property
	def timestamp(self):
		"""
		The timestamp of the start of the current tick.
		:rtype: ``long``
		:return: The timestamp.
		"""
		return _datetime_to_ts(self.time)

	@property
	def is_using_limiter(self):
		"""
		Whether frame-limiting functionality is enabled. If this is true, calls to advance() wait until the full frame
		time has passed, and frames that take too long are marked as such by setting is_slow. If this is False, calls to
		advance() happen instantly regardless of the current speed, and ticks will never be marked as running slowly.
		:rtype: ``bool``
		:return: Whether the previous tick missed its target for execution time.
		"""
		return self._limiter_enabled

	@property
	def is_slow(self):
		"""
		Whether the execution of the previous tick's operations took longer than the target tick speed. In this case, if
		possible, the following tick should try to limit its actions to try and 'speed up' the its execution in order to
		return to the target time.
		:rtype: ``bool``
		:return: Whether the previous tick missed its target for execution time.
		"""
		return self._is_slow

	@property
	def is_active(self):
		"""
		Whether the clock has been started with a call to start().
		:rtype: ``bool``
		:return: Whether the clock has started.
		"""
		return self._clock_active

	@property
	def is_suspended(self):
		"""
		Whether the clock is currently suspended via a call to suspend().
		:rtype: ``bool``
		:return: Whether the clock is suspended.
		"""
		return self._clock_suspended

	@property
	def is_running(self):
		"""
		Whether the clock is both active and not supended.
		:rtype: ``bool``
		:return: Whether the clock is running.
		"""
		return self.is_active and not self.is_suspended

	def to_json(self):
		"""
		Converts this time into a dictionary for exteral storage.
		:rtype: ``dict[str, Any]``
		:return: The dictionary.
		"""
		data = {'tick': self.tick, 'active': self.is_active}
		if self._clock_active:
			data['speed'] = self.speed.total_seconds()
			data['total'] = self.total.total_seconds()
			data['suspended'] = self.is_suspended
			data['frame_limiter'] = self.is_using_limiter
		return data

	@staticmethod
	def from_json(json):
		tick = int(json['tick'])
		active = bool(json['active'])
		limiter = bool(json.get('frame_limiter', True))
		if active:
			speed = float(json['speed'])
			total = datetime.timedelta(seconds=float(json['total']))
			suspended = bool(json['suspended'])
			return TickClock(tick, speed, total, suspended, limiter_enabled=limiter)
		else:
			return TickClock(tick, limiter_enabled=limiter)

	def _set_clock_props(self, speed, total=None):
		"""
		:type speed: ``datetime.timedelta``
		:type total: ``datetime.timedelta``
		:return:
		"""
		self._time = now()
		self._speed = speed
		if total is not None:
			self._total = total
		else:
			self._total = datetime.timedelta(seconds=0.0)
		self._prev = self._time - self._speed
		self._is_slow = False
		self._elapsed = self._speed
		self._prev_target_time = self._time

	def _increment_clock_props(self, ts):
		self._prev = self._time
		self._tick += 1
		self._time = ts
		self._elapsed = self._time - self._prev
		self._is_slow = self._limiter_enabled and (self.elapsed - self.speed > self._target_tolerance)
		self._total += self._elapsed

	def __str__(self):
		return "<T=" + str(self.tick) + ">"

	def __repr__(self):
		return type(TickClock, self).__name__ + "(tick=" + repr(self.tick) + ")"


def now() -> datetime.datetime:
	"""
	Gets the current datetime as a timezone-aware UTC datetime instance.

	:return: The current datetime.
	"""
	dt = datetime.datetime.utcnow()
	dt = dt.replace(tzinfo=datetime.timezone.utc)
	return dt


def _datetime_to_ts(utc: datetime.datetime, ms: bool=False) -> int:
	"""
	Converts a UTC timezone-aware datetime into a unix-epoch timestamp.
	:param utc: The datetime to convert. Must be in UTC timezone, or at least be timezone-aware.
	:param ms: Whether to output the timestamp in milliseconds rather than seconds. If false, it is returned in seconds.
	:return: The timestamp for the given date.
	"""
	if utc.utcoffset() is None:
		raise ValueError("Datetime is not tz-aware")
	utc = utc.astimezone(datetime.timezone.utc)
	ts = time.mktime(utc.utctimetuple())
	if ms:
		ts += utc.microsecond / 1000000.0
		ts *= 1000
	return int(ts)


def now_ts(ms: bool=False) -> int:
	"""
	Gets the current datetime as a timestamp representing the number of seconds since the start of the unix epoch.
	:param ms: Whether to return the timestamp in milliseconds rather than seconds. If false, it is returned in seconds.
	:return: The timestamp of the current time.
	"""
	return _datetime_to_ts(now(), ms=ms)
