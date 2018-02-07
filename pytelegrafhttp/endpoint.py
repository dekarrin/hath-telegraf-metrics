"""
Endpoint data and text scraper.
"""
import logging
from .util import VerificationError

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class Endpoint(object):

	def __init__(self, uri, verify_pattern):
		"""
		Create a new Endpoint.
		:param uri: The uri of the endpoint.
		:param verify_pattern: The pattern to use to confirm that the contents are correct.
		"""
		self.uri = uri
		self.verify_pattern = verify_pattern

	def scrape_metric(self, metric, endpoint_text, idx=0):
		if self.verify_pattern.search(endpoint_text) is None:
			raise VerificationError("endpoint did not match expected content", endpoint_text)
		dest_channel = metric['dest']
		metric_name = metric['name']
		pattern = metric['regex']
		metric_value_definitions = metric['values']
		metric_tag_definitions = metric['tags']

		if pattern.search(endpoint_text) is None:
			warning_text = "metric " + str(idx) + " (" + metric_name + ") for endpoint + '" + self.uri + "'"
			warning_text += " could not be found. Skipping for this unit of time"
			_log.warning(warning_text)
			return None

		bursts = []
		# find all matches
		matchers = pattern.finditer(endpoint_text)
		for matcher in matchers:
			# build the values from the matched items
			metric_values = {}
			for value_def in metric_value_definitions:
				value_name = value_def['name']
				value_type = value_def['type']
				value_conv = value_def['conversion']
				if value_type == 'capture':
					value_group = value_def['capture']
					val = matcher.group(value_group)
					metric_values[value_name] = value_conv(val)
				elif value_type == 'custom':

					metric_values[value_name] = value_conv(matcher)
				elif value_type == 'const':
					metric_values[value_name] = value_conv
				else:
					# should be caught during config parsing, but double-check
					raise ValueError("Bad metric value definition type: " + repr(value_type))

			metric_tags = {}
			for tag_name in metric_tag_definitions:
				tag_def = metric_tag_definitions[tag_name]
				tag_type = tag_def['type']
				if tag_type == 'capture':
					tag_value = matcher.group(tag_def['value'])
				elif tag_type == 'const':
					tag_value = tag_def['value']
				else:
					# should be caught during config parsing, but double-check
					raise ValueError("Bad metric tag definition type: " + repr(tag_type))
				metric_tags[tag_name] = tag_value

			bursts.append({
				'channel': dest_channel,
				'metric': metric_name,
				'values': metric_values,
				'tags': metric_tags
			})
		return bursts

	def scrape_all_metrics(self, metrics, endpoint_text):
		if self.verify_pattern.search(endpoint_text) is None:
			raise VerificationError("endpoint did not match expected content", endpoint_text)
		idx = 0
		all_bursts = []
		for m in metrics:
			bursts = self.scrape_metric(m, endpoint_text, idx=idx)
			if bursts is not None:
				all_bursts += bursts
			idx += 1
		return all_bursts
