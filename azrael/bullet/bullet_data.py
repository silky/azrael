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
Define the State Variables structure and its cencoding.

The state variables are encapsulated by the named tuple ``BulletData``. This
module contains the necessary conversions to/from binary, as well as a
conversion to NumPy. The NumPy conversion is only necessary for the Cython
wrapper to Bullet and will eventually move out of here.
"""

import sys
import logging
import pymongo
import IPython
import numpy as np
import azrael.util
import azrael.config as config

from collections import namedtuple
from azrael.typecheck import typecheck
from azrael.protocol_json import loads, dumps

ipshell = IPython.embed

# All relevant physics data.
_BulletData = namedtuple('BulletData',
                         'radius scale imass restitution orientation '
                         'position velocityLin velocityRot cshape')


class BulletData(_BulletData):
    """
    Return a ``BulletData`` object.

    Without any arguments this function will return a valid ``BulletData``
    specimen with sensible defaults.

    :return Booster: compiled booster description.
    """
    @typecheck
    def __new__(cls, radius: (int, float)=1, scale: (int, float)=1,
                imass: (int, float)=1,
                restitution: (int, float)=0.9,
                orientation: (list, np.ndarray)=[0, 0, 0, 1],
                position: (list, np.ndarray)=[0, 0, 0],
                vlin: (list, np.ndarray)=[0, 0, 0],
                vrot: (list, np.ndarray)=[0, 0, 0],
                cshape: (list, np.ndarray)=[0, 1, 1, 1]):

        # Convert arguments to NumPy types where necessary.
        orientation = np.array(orientation, np.float64)
        position = np.array(position, np.float64)
        velocityLin = np.array(vlin, np.float64)
        velocityRot = np.array(vrot, np.float64)
        cshape = np.array(cshape, np.float64)

        # Sanity checks.
        assert len(orientation) == 4
        assert len(position) == 3
        assert len(velocityLin) == 3
        assert len(velocityRot) == 3
        assert len(cshape) == 4

        # Build the actual named tuple.
        self = super().__new__(
            cls,
            radius=radius,
            scale=scale,
            imass=imass,
            restitution=restitution,
            orientation=np.float64(orientation),
            position=np.float64(position),
            velocityLin=np.float64(vlin),
            velocityRot=np.float64(vrot),
            cshape=np.float64(cshape))
        return self

    def __eq__(self, ref):
        """
        Two ``BulletData`` instances are considered equal their content matches
        well.

        Small rounding errors are possible, especially when Bullet is involved
        since it uses 32Bit data types internally.
        """
        # Sanity check.
        if not isinstance(ref, type(self)):
            return False

        # Test all fields except cshape.
        for f in self._fields:
            if f == 'cshape':
                continue
            if not np.allclose(getattr(self, f), getattr(ref, f), atol=1E-9):
                return False
        return True

    def __ne__(self, ref):
        return not self.__eq__(ref)

    def tojson(self):
        """
        Convert ``BulletData`` to UTF8 encoded JSON.
        """
        d = {'part': 'BulletData'}
        for f in self._fields:
            d[f] = getattr(self, f)
        return dumps(d)

    @typecheck
    def toNumPyString(self):
        """
        Return the NumPy array of this BulletData structure.

        The returned NumPy array is binary compatible with the `cython_bullet`
        wrapper and, ideally, the only way how data is encoded for Bullet.

        :return ndarray: NumPy.float64 array.
        """
        # Allocate a NumPy array for the state variable data.
        buf = np.zeros(config.LEN_SV_FLOATS, dtype=np.float64)

        # Convert the content of ``self`` to float64 NumPy data and insert them
        # into the buffer. The order *matters*, as it is the exact order in
        # which the C++ wrapper for Bullet expects the data.
        buf[0] = np.float64(self.radius)
        buf[1] = np.float64(self.scale)
        buf[2] = np.float64(self.imass)
        buf[3] = np.float64(self.restitution)
        buf[4:8] = np.float64(self.orientation)
        buf[8:11] = np.float64(self.position)
        buf[11:14] = np.float64(self.velocityLin)
        buf[14:17] = np.float64(self.velocityRot)
        buf[17:21] = np.float64(self.cshape)

        # Just to be sure because an error here may lead to subtle bugs with
        # the Bullet C++ interface.
        assert buf.dtype == np.float64
        return buf


@typecheck
def fromjson(data: bytes):
    """
    Unpack the JSON encoded ``BulletData`` in ``data``.
    """
    d = loads(data)
    args = [d[_] for _ in BulletData._fields]
    return BulletData(*args)


@typecheck
def fromNumPyString(buf: np.ndarray):
    """
    Return the ``BulletData`` that corresponds to ``buf``.

    The ``buf`` argument constitutes a serialised NumPy array.

    :param ndarray obj: serialised NumPy array.
    :return BulletData: ``BulletData`` instance.
    """
    assert len(buf) == config.LEN_SV_FLOATS

    data = BulletData(
        radius=buf[0],
        scale=buf[1],
        imass=buf[2],
        restitution=buf[3],
        orientation=buf[4:8],
        position=buf[8:11],
        vlin=buf[11:14],
        vrot=buf[14:17],
        cshape=buf[17:21])
    return data