# Copyright 2014, Oliver Nagy <olitheolix@gmail.com>
#
# This file is part of Azrael (https://github.com/olitheolix/azrael)
#
# Azrael is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Azrael is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Azrael. If not, see <http://www.gnu.org/licenses/>.

"""
Global configuration parameters.
"""
import sys
import logging
import netifaces

# ---------------------------------------------------------------------------
# Configure logging.
# ---------------------------------------------------------------------------

# Specify the log level for Azrael.
log_file = 'azrael.log'
logger = logging.getLogger('azrael')

# Prevent it from logging to console no matter what.
logger.propagate = False

# Create a handler instance to log the messages to stdout.
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.DEBUG)
#console.setLevel(logging.ERROR)

logFormat = '%(levelname)s - %(name)s - %(message)s'
console.setFormatter(logging.Formatter(logFormat))

# Install the handler.
logger.addHandler(console)

# Specify a file logger.
logFormat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(logFormat)
fileHandler = logging.FileHandler(log_file, mode='a')
fileHandler.setLevel(logging.DEBUG)
fileHandler.setFormatter(formatter)
fileHandler.setLevel(logging.DEBUG)

# Install the handler.
logger.addHandler(fileHandler)

del console, logFormat, formatter, fileHandler

# ---------------------------------------------------------------------------
# Global variables.
# ---------------------------------------------------------------------------

# Port of Tornado server.
webserver_port = 8080

# Determine the host IP address. Try eth0  first. Use localhost is a fallback
# option if no configured ethernet card was found.
try:
    host_ip = netifaces.ifaddresses('eth0')[2][0]['addr']
except (ValueError, KeyError):
    try:
        host_ip = netifaces.ifaddresses('lo')[2][0]['addr']
    except (ValueError, KeyError):
        logger.critical('Could not find a valid network interface')
        sys.exit(1)

# Address of the various Azrael services.
addr_clerk = 'tcp://' + host_ip + ':5555'
addr_leonard_pushpull = 'tcp://' + host_ip + ':5556'
