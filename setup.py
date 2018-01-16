from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
	long_description = f.read()

setup(
	name='pytelegrafhttp',
	version='0.1.0',
	description='Scrape HTTP pages for metrics and feed them into Telegraf',
	long_description=long_description,
	url='https://github.com/dekarrin/pytelegrafhttp',
	author='Rebecca C. Nelson',
	classifiers=[
		'Development Status :: 3 - Alpha',
		'Environment :: Console',
		'Intended Audience :: Developers',
		'License :: OSI Approved :: MIT License',
		'Programming Language :: Python :: 3 :: Only',
		'Topic :: System'
	],
	keywords='telegraf metrics http.py',
	packages=['pytelegrafhttp'],
	install_requires=['pytelegraf', 'requests'],
	python_requires='>=3.3',
	extras_require={
		'systemd-logs': ['systemd-python']
	},
	entry_points={
		'console_scripts': [
			'pytelhttp=pytelegrafhttp:main'
		]
	}
)