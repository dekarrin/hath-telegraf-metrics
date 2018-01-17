# Global default install directory for all files. Note that each specific file / directory may override where it is
# located, but by default they are all grouped together
install_dir = '/etc/pytelegrafhttp'

###############
# ENVIRONMENT #
###############

# Directory for files for use with daemon communication
env_daemon_files_dir = install_dir + '/daemon'


########
# TIME #
########

# How often metrics are collected. Measured in seconds.
time_collection_interval = 60


###########
# LOGGING #
###########

# Location of log file directory (by default all logs are kept together; override individual log file paths to change
# this).
log_dir = install_dir + '/logs'

# Location of log file that contains all output
log_main_log_path = log_dir + '/main.log'

# Location of log file that contains only errors
log_error_log_path = log_dir + '/errors.log'

# Maximum size of a log file before it is rotated. Format is flexible, and accepts strings such as "24KB", "8g", or
# "5kbs"
log_file_max_size = "5 Mbs"

# Number of log files to keep. Once this number of rotated logs is reached, every rotation after that will cause the
# oldest one to be deleted.
log_file_keep_count = 4

# Additional system log to use. Adding one of these values requires that the associated python module is installed on
# the host system separately from this application.
#
# Supported values are: 'systemd'
log_os_logs = []
# Uncomment to enable journalctl logging
# log_os_logs.append('systemd')


###########
# SCRAPER #
###########

scraper_host = 'e-fancomics.org'
scraper_username = 'username'
scraper_password = 'password'
scraper_use_ssl = True
scraper_login_steps = [
	('attempt', {'endpoint': '/fancomicsathome.php'}),
	('resp-extract', {'type': 'form-vars', 'inject': {'UserName': 'username', 'PassWord': 'password'}}),
	('submit-form', {}),
	('bounce-transfer', {'pattern': '<a href="([^"]+)">Or click here if you do not wish to wait</a>'}),
	('verify', {'pattern': 'F@H Miss% shows the percentage of requests'})
]
scraper_endpoints = []
scraper_endpoints.append({
	'endpoint': '/fancomicsathome.php',
	'verify-pattern': 'F@H Miss% shows the percentage of requests',
	'metrics': [
		{
			'dest': 'hath-net',  # destination db / telegraf identifier
			'name': 'hath-net',  # metrics name
			'regex': [
				r'<td>North and South America</td>\s*',
				r'<td [^>]*>[^ ]+ Gbits/s</td>\s*',
				r'<td [^>]*>=</td>\s*',
				r'<td [^>]*>([^ ]+) MB/s</td>\s*',
				r'<td [^>]*>([^ ]+) %</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>',
			],
			'values': [
				{'name': 'load', 'type': int, 'capture': 1},
				{'name': 'miss-rate', 'type': float, 'capture': 2},
				{'name': 'coverage', 'type': float, 'capture': 3},
				{'name': 'hits-per-gb', 'type': float, 'capture': 4},
				{'name': 'quality', 'type': int, 'capture': 5}
			],
			'tags': {'region': 'americas'}
		},
		{
			'dest': 'hath-net',
			'name': 'hath-net',
			'regex': [
				r'<td>Europe and South America</td>\s*',
				r'<td [^>]*>[^ ]+ Gbits/s</td>\s*',
				r'<td [^>]*>=</td>\s*',
				r'<td [^>]*>([^ ]+) MB/s</td>\s*',
				r'<td [^>]*>([^ ]+) %</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>',
			],
			'values': [
				{'name': 'load', 'type': int, 'capture': 1},
				{'name': 'miss-rate', 'type': float, 'capture': 2},
				{'name': 'coverage', 'type': float, 'capture': 3},
				{'name': 'hits-per-gb', 'type': float, 'capture': 4},
				{'name': 'quality', 'type': int, 'capture': 5}
			],
			'tags': {'region': 'europe-africa'}
		},
		{
			'dest': 'hath-net',
			'name': 'hath-net',
			'regex': [
				r'<td>Asia and Oceania</td>\s*',
				r'<td [^>]*>[^ ]+ Gbits/s</td>\s*',
				r'<td [^>]*>=</td>\s*',
				r'<td [^>]*>([^ ]+) MB/s</td>\s*',
				r'<td [^>]*>([^ ]+) %</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>',
			],
			'values': [
				{'name': 'load', 'type': int, 'capture': 1},
				{'name': 'miss-rate', 'type': float, 'capture': 2},
				{'name': 'coverage', 'type': float, 'capture': 3},
				{'name': 'hits-per-gb', 'type': float, 'capture': 4},
				{'name': 'quality', 'type': int, 'capture': 5}
			],
			'tags': {'region': 'asia-oceania'}
		},
		{
			'dest': 'hath-net',
			'name': 'hath-net',
			'regex': [
				r'<td>Global</td>\s*',
				r'<td [^>]*>[^ ]+ Gbits/s</td>\s*',
				r'<td [^>]*>=</td>\s*',
				r'<td [^>]*>([^ ]+) MB/s</td>\s*',
				r'<td [^>]*>([^ ]+) %</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>',
			],
			'values': [
				{'name': 'load', 'type': int, 'capture': 1},
				{'name': 'miss-rate', 'type': float, 'capture': 2},
				{'name': 'coverage', 'type': float, 'capture': 3},
				{'name': 'hits-per-gb', 'type': float, 'capture': 4},
				{'name': 'quality', 'type': int, 'capture': 5}
			],
			'tags': {'region': 'global'}
		},
		{
			'dest': 'hath-client-net-stats',
			'name': 'hath-health',
			'regex': [
				r'<tr>\s*',
				r'<td><a [^>]*>([^<]+)</td>\s*',
				r'<td>([^<]+)</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td>[^<]*</td>\s*',
				r'<td>[^<]*</td>\s*',
				r'<td>([^<]+)</td>\s*',
				r'<td [^>]*>[^<]+</td>\s*',
				r'<td>[^<]*</td>\s*',
				r'<td>[^<]*</td>\s*',
				r'<td>[^<]*</td>\s*',
				r'<td [^>]*>([^<]+)</td>\s*',
				r'<td>([^<]+)</td>\s*',
				r'<td>([^ ]+) / min</td>\s*',
				r'<td>([^ ]+) / day</td>\s*',
			],
			'values': [
				{'name': 'online', 'type': lambda s: s == 'Online', 'capture': 3},
				{'name': 'files', 'type': int, 'capture': 4},
				{'name': 'trust', 'type': int, 'capture': 5},
				{'name': 'quality', 'type': int, 'capture': 6},
				{'name': 'hitrate', 'type': float, 'capture': 7}
			],
			'tags': {
				'host': 'CAPTURE-1',
				'client-id': 'CAPTURE-2',
			}
		}
	]
})
