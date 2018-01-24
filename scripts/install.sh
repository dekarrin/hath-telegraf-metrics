#!/bin/bash

E_USER_REQS=1
E_BUILD=2
E_USER_CREATION=3
E_ETC=4

# Installs pytelegraf on debian-like systems. Requires systemd.
[ "$(id -u)" -eq 0 ] || { echo "Must be run as root" >&2; exit ${E_USER_REQS};}
hash systemctl 2>/dev/null || { echo "Systemd required but not installed. Abort." >&2; exit ${E_USER_REQS};}

[ $# -ge 1 ] || { echo "User to install python command as must be given as first argument" >&2; exit ${E_USER_REQS};}

command_user="$1"
id -u "$command_user" >/dev/null 2>&1 || { echo "User '$command_user' does not appear to exist. Cannot install command as user"; exit ${E_USER_REQS};}

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
install_dir=/etc/pytelegrafhttp

# build python wheel and install with pip
cd "$script_dir/.."
su --preserve-environment -c 'python3 setup.py install' "$command_user" || { echo "Could not build/install wheel file" >&2; exit ${E_BUILD};}

# create system user
if ! id pytelegrafhttp >/dev/null 2>&1
then
	useradd -M -U -r pytelegrafhttp || { echo "Could not create pytelegrafhttp user" >&2; exit ${E_USER_CREATION};}
fi

# create install directory
if ! [ -d "$install_dir" ]
then
	mkdir "$install_dir" || { echo "Could not create $install_dir directory" >&2; exit ${E_ETC};}
	chown pytelegrafhttp:pytelegrafhttp "$install_dir" || { echo "Could not set owner of install directory" >&2; exit ${E_ETC};}
	chmod 775 "$install_dir" || { echo "Could not set mode of install directory" >&2; exit ${E_ETC};}
fi

# create logs directory
if ! [ -d "$install_dir/logs" ]
then
	mkdir "$install_dir/logs" || { echo "Could not create logs directory" >&2; exit ${E_ETC};}
	chown pytelegrafhttp:pytelegrafhttp "$install_dir/logs" || { echo "Could not set owner of logs directory" >&2; exit ${E_ETC};}
	chmod 775 "$install_dir/logs" || { echo "Could not set mode of logs directory" >&2; exit ${E_ETC};}
fi

# create daemon directory
if ! [ -d "$install_dir/daemon" ]
then
	mkdir "$install_dir/daemon" || { echo "Could not create daemon directory" >&2; exit ${E_ETC};}
	chown pytelegrafhttp:pytelegrafhttp "$install_dir/daemon" || { echo "Could not set owner of daemon directory" >&2; exit ${E_ETC};}
	chmod 770 "$install_dir/daemon" || { echo "Could not set mode of daemon directory" >&2; exit ${E_ETC};}
fi

# create initial config
cp config.example.py "$install_dir/config.py" || { echo "Could not create main config" >&2; exit ${E_ETC};}
# attempt to add systemd logging
sed -e 's/# (log_os_logs\.append\('\''systemd'\''\))/\1/' "$install_dir/config.py" > "$install_dir/config.new"
mv "$install_dir/config.new" "$install_dir/config.py"
chown pytelegrafhttp:pytelegrafhttp "$install_dir/config.py" || { echo "Could not set owner of config.py" >&2; exit ${E_ETC};}
chmod 770 "$install_dir/config.py" || { echo "Could not set mode of config.py" >&2; exit ${E_ETC};}

# create systemd service file
cp scripts/pytelegrafhttp.service "$install_dir/pytelegrafhttp.service" || { echo "Could not create systemd unit file" >&2; exit ${E_ETC};}
ln -s "$install_dir/pytelegrafhttp.service" /etc/systemd/system/pytelegrafhttp.service || { echo "Could not create unit file symlink" >&2; exit ${E_ETC};}

echo "installation completion"
echo "main config located in '$install_dir/config.py'"
echo "Unit file symlinked as 'pytelegrafhttp.service'."
echo 'To start, do `systemctl start pytelegrafhttp`'
