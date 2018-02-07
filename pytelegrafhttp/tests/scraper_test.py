from unittest import TestCase


class ScraperTest(TestCase):
	def test_initial(self):
		myVar = "true"
		self.assertTrue(myVar, "myvar is not true")
