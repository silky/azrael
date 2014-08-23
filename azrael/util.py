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


import numpy as np
import azrael.config as config


class Timer(object):
    def __init__(self, verbose=False, msg='Elapsed Time: '):
        self.verbose = verbose
        self.prefix = msg

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.elapsed = self.end - self.start
        self.secs = int(self.elapsed)
        self.msecs = int(self.elapsed * 1E3)
        self.usecs = int(self.elapsed * 1E6)

        if self.verbose:
            print(self.prefix + '{}'.format(self.format(self.elapsed)))

    def format(self, elapsed):
        return '{0:,}us'.format(int(elapsed * 1E6))


def int2id(objID: int):
    """
    Convert an integer to the corresponding object ID.

    This function will raise an `OverflowError` if ``objID`` is too large for
    the available number of bytes.
    """
    assert isinstance(objID, int)
    assert objID >= 0
    assert objID < 2 ** 63
    return np.int64(objID).tostring()


def id2int(objID: int):
    """
    Convert an object ID to the corresponding integer.
    """
    assert isinstance(objID, bytes)
    assert len(objID) == 8
    return int(np.fromstring(objID, np.int64)[0])
