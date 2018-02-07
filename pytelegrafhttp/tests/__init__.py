
def discover():
	from unittest import TestLoader

	loader = TestLoader()
	return loader.discover('pytelegrafhttp/tests', pattern='*_test.py')
