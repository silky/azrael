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
Specify and implement the necessary functions to create, access and manipulate
state variables.
"""

import sys
import logging
import IPython
import numpy as np
import azrael.util as util
import azrael.config as config
import azrael.database as database
import azrael.bullet.bullet_data as bullet_data

from collections import namedtuple
from azrael.typecheck import typecheck

ipshell = IPython.embed

# Convenience.
BulletDataOverride = bullet_data.BulletDataOverride

# Return value signature.
RetVal = util.RetVal

# Create module logger.
logit = logging.getLogger('azrael.' + __name__)


def getNumObjects():
    """
    Return the number of objects in the simulation.

    :returns int: number of objects in simulation.
    """
    return database.dbHandles['SV'].count()


@typecheck
def getCmdSpawn():
    """
    Return all queued "Spawn" commands.

    The commands remain in the DB and successive calls to this function will
    thus return the previous results.

    :return: objects as inserted by ``spawn``.
    :rtype: list of dicts.
    """
    return RetVal(True, None, list(database.dbHandles['CmdSpawn'].find()))

@typecheck
def getCmdModifyStateVariables():
    """
    Return all queued "Modify" commands.

    The commands remain in the DB and successive calls to this function will
    thus return the previous results.

    :return: objects as inserted by ``setStateVariable``.
    :rtype: list of dicts.
    """
    return RetVal(True, None, list(database.dbHandles['CmdModify'].find()))

@typecheck
def getCmdRemove():
    """
    Return all queued "Remove" commands.

    The commands remain in the DB and successive calls to this function will
    thus return the previous results.

    :return: objects as inserted by ``removeObject``.
    :rtype: list of dicts.
    """
    return RetVal(True, None, list(database.dbHandles['CmdRemove'].find()))

@typecheck
def dequeueCmdSpawn(spawn: list):
    """
    De-queue ``spawn`` commands from "Spawn" queue.

    Non-existing documents do not count and will be silently ignored.

    :param list spawn: Mongo documents to remove from "Spawn"
    :return int: number of de-queued commands
    """
    ret = database.dbHandles['CmdSpawn'].remove({'objid': {'$in': spawn}})
    return RetVal(True, None, ret['n'])


@typecheck
def dequeueCmdModify(modify: list):
    """
    De-queue ``modify`` commands from "Modify" queue.

    Non-existing documents do not count and will be silently ignored.

    :param list modify: list of Mongo documents to de-queue.
    :return: number of de-queued commands
    :rtype: tuple
    """
    ret = database.dbHandles['CmdModify'].remove({'objid': {'$in': modify}})
    return RetVal(True, None, ret['n'])


@typecheck
def dequeueCmdRemove(remove: list):
    """
    De-queue ``remove`` commands from "Remove" queue.

    Non-existing documents do not count and will be silently ignored.

    :param list spawn: list of Mongo documents to de-queue.
    :return: number of de-queued commands
    :rtype: tuple
    """
    ret = database.dbHandles['CmdRemove'].remove({'objid': {'$in': remove}})
    return RetVal(True, None, ret['n'])


@typecheck
def addCmdSpawn(objID: bytes, sv: bullet_data.BulletData, aabb: (int, float)):
    """
    Enqueue a new object with ``objID`` for Leonard to spawn.

    Contrary to what the name ``aabb`` suggests, this actually denotes a
    bounding sphere and thus requires only a scalar argument instead of 3 side
    lengths. This will change eventually to become a proper AABB.

    Returns **False** if ``objID`` already exists or is already queued.

    Leonard will apply this request once per physics cycle but it is impossible
    to determine when exactly.

    :param bytes objID: object ID to insert.
    :param bytes sv: encoded state variable data.
    :param float aabb: size of AABB.
    :return: success.
    """
    # Serialise SV.
    sv = sv.toJsonDict()

    # Sanity checks.
    if len(objID) != config.LEN_ID:
        return RetVal(False, 'objID has wrong length', None)
    if aabb < 0:
        msg = 'AABB must be non-negative'
        logit.warning(msg)
        return RetVal(False, msg, None)

    # Meta data for spawn command.
    data = {'objid': objID, 'sv': sv, 'AABB': float(aabb)}

    # This implements the fictitious "insert_if_not_yet_exists" command. It
    # will return whatever the latest value from the DB, which is either the
    # one we just inserted (success) or a previously inserted one (fail). The
    # only way to distinguish them is to verify that the SVs are identical.
    doc = database.dbHandles['CmdSpawn'].find_and_modify({'objid': objID},
                                       {'$setOnInsert': data},
                                       upsert=True, new=True)
    success = doc['sv'] == data['sv']

    # Return success status to caller.
    if success:
        return RetVal(True, None, None)
    else:
        return RetVal(False, None, None)


@typecheck
def addCmdRemoveObject(objID: bytes):
    """
    Remove ``objID`` from the physics simulation.

    Leonard will apply this request once per physics cycle but it is impossible
    to determine when exactly.

    .. note:: This function always succeeds.

    :param bytes objID: ID of object to delete.
    :return: Success.
    """
    data = {'del': objID}
    doc = database.dbHandles['CmdRemove'].find_and_modify(
        {'objid': objID}, {'$setOnInsert': data}, upsert=True, new=True)
    return RetVal(True, None, None)


@typecheck
def addCmdModifyStateVariable(objID: bytes, data: BulletDataOverride):
    """
    Queue request to Override State Variables of ``objID`` with ``data``.

    Leonard will apply this request once per physics cycle but it is impossible
    to determine when exactly.

    :param bytes objID: object to update.
    :param BulletDataOverride pos: new object attributes.
    :return bool: Success
    """
    # Sanity check.
    if (len(objID) != config.LEN_ID):
        return RetVal(False, 'objID has invalid length', None)

    # Do nothing if data is None.
    if data is None:
        return RetVal(True, None, None)

    # Make sure that ``data`` is really valid by constructing a new
    # BulletDataOverride instance from it.
    data = BulletDataOverride(*data)
    if data is None:
        return RetVal(False, 'Invalid override data', None)

    # All fields in ``data`` (a BulletDataOverride instance) are, by
    # definition, one of {None, int, float, np.ndarray}. The following code
    # merely converts the  NumPy arrays to normal lists so that Mongo can store
    # them. For example, BulletDataOverride(None, 2, array([1,2,3]), ...)
    # would become [None, 2, [1,2,3], ...].
    data = list(data)
    for idx, val in enumerate(data):
        if isinstance(val, np.ndarray):
            data[idx] = val.tolist()

    # Save the new SVs to the DB (overwrite existing ones).
    doc = database.dbHandles['CmdModify'].find_and_modify(
        {'objid': objID}, {'$setOnInsert': {'sv': data}},
        upsert=True, new=True)

    # This function was successful if exactly one document was updated.
    return RetVal(True, None, None)


@typecheck
def addCmdSetForceAndTorque(objID: bytes, force: np.ndarray, torque: np.ndarray):
    """
    Set the central ``force`` and ``torque`` acting on ``objID``.

    This function always suceeds.

    .. note::
       The force always applies to the centre of the mass only, unlike the
       ``setForce`` function which allows for position relative to the centre
       of mass.

    :param bytes objID: the object
    :param ndarray force: apply this central ``force`` to ``objID``.
    :param ndarray torque: apply this ``torque`` to ``objID``.
    :return bool: Success
    """
    # Sanity check.
    if (len(objID) != config.LEN_ID):
        return RetVal(False, 'objID has invalid length', None)
    if not (len(force) == len(torque) == 3):
        return RetVal(False, 'force or torque has invalid length', None)

    # Serialise the force and torque.
    force = force.astype(np.float64).tostring()
    torque = torque.astype(np.float64).tostring()

    # Update the DB.
    ret = database.dbHandles['CmdForce'].update(
        {'objid': objID},
        {'$set': {'central_force': force, 'torque': torque}},
        upsert=True)

    return RetVal(True, None, None)


@typecheck
def getStateVariables(objIDs: (list, tuple)):
    """
    Retrieve the state variables for all ``objIDs``.

    Return *None* for every entry non-existing objID.

    :param iterable objIDs: list of object IDs for which to return the SV.
    :return dict: dictionary of the form {objID: sv}
    """
    # Sanity check.
    for _ in objIDs:
        if not isinstance(_, bytes) or (len(_) != config.LEN_ID):
            msg = 'Object ID has invalid type'
            logit.warning(msg)
            return RetVal(False, msg, None)

    # Retrieve the state variables.
    out = {_: None for _ in objIDs}
    for doc in database.dbHandles['SV'].find({'objid': {'$in': objIDs}}):
        out[doc['objid']] = bullet_data.fromJsonDict(doc['sv'])
    return RetVal(True, None, out)


@typecheck
def getAABB(objIDs: (list, tuple)):
    """
    Retrieve the AABBs for all ``objIDs``.

    This function returns the AABBs (or *None* if it does not exist) for all
    ``objIDs``.

    :param iterable objIDs: list of object ID for which to return the SV.
    :return: size of AABBs.
    :rtype: list of *floats*.
    """
    # Sanity check.
    for _ in objIDs:
        if not isinstance(_, bytes) or (len(_) != config.LEN_ID):
            msg = 'Object ID has invalid type'
            logit.warning(msg)
            return RetVal(False, msg, None)

    # Retrieve the state variables.
    out = list(database.dbHandles['SV'].find({'objid': {'$in': objIDs}}))

    # Put all AABBs into a dictionary to simplify sorting afterwards.
    out = {_['objid']: np.array(_['AABB'], np.float64) for _ in out}

    # Compile the AABB values into a list ordered by ``objIDs``. Insert a None
    # element if a particular objID has no AABB (probably means the object was
    # recently deleted).
    out = [out[_] if _ in out else None for _ in objIDs]

    # Return the AABB values.
    return RetVal(True, None, out)


@typecheck
def _updateBulletDataTuple(orig: bullet_data.BulletData,
                           new: bullet_data.BulletDataOverride):
    """
    Overwrite fields in ``orig`` with content of ``new``.

    If one or more fields in ``new`` are *None* then the original value in
    ``orig`` will not be modified.

    This is a convenience function. It avoids code duplication which was
    otherwise unavoidable because not all Leonard implementations inherit the
    same base class.

    :param BulletData orig: the original tuple.
    :param BulletDataOverride new: the new values (*None* entries are ignored).
    :return: updated version of ``orig``.
    :rtype: BulletData
    """
    if new is None:
        return orig

    # Convert the named tuple ``orig`` into a dictionary.
    fields = orig._fields
    dict_orig = {_: getattr(orig, _) for _ in fields}

    # Copy all not-None values from ``new`` into ``dict_orig``.
    for k, v in zip(fields, new):
        if v is not None:
            dict_orig[k] = v

    # Build a new BulletData instance and return it.
    return bullet_data.BulletData(**dict_orig)


def getAllStateVariables():
    """
    Return a dictionary of {objID: SV} all objects in the simulation.

    The keys and values of the returned dictionary correspond to the object ID
    and their associated State Vectors, respectively.

    :return: dictionary of state variables with object IDs as keys.
    :rtype: dict
    """
    # Compile all object IDs and state variables into a dictionary.
    out = {}
    for doc in database.dbHandles['SV'].find():
        key, value = doc['objid'], bullet_data.fromJsonDict(doc['sv'])
        out[key] = value
    return RetVal(True, None, out)


def getAllObjectIDs():
    """
    Return all object IDs in the simulation.

    :return: list of all object IDs in the simulation.
    :rtype: list
    """
    # Compile and return the list of all object IDs.
    out = [_['objid'] for _ in database.dbHandles['SV'].find()]
    return RetVal(True, None, out)


@typecheck
def setForce(objID: bytes, force: np.ndarray, relpos: np.ndarray):
    """
    Update the ``force`` acting on ``objID``.

    This function is a wrapper around ``addCmdSetForceAndTorque``.

    :param bytes objID: recipient of ``force``
    :param np.ndarray force: the ``force`` (in Newton).
    :param np.ndarray relpos: position of ``force`` relative to COM.
    :return bool: success.
    """
    # Sanity check.
    if (len(objID) != config.LEN_ID):
        return RetVal(False, 'objID has invalid length', None)
    if not (len(force) == len(relpos) == 3):
        return RetVal(False, 'force or relpos have invalid length', None)

    # Compute the torque and then call addCmdSetForceAndTorque.
    torque = np.cross(relpos, force)
    ret = addCmdSetForceAndTorque(objID, force, torque)
    if ret.ok:
        return RetVal(True, None, None)
    else:
        return RetVal(False, ret.msg, None)


@typecheck
def getForceAndTorque(objID: bytes):
    """
    Return the force and torque for ``objID``.

    :param bytes objID: object for which to return the force and torque.
    :returns: force and torque as {'force': force, 'torque': torque}.
    :rtype: dict
    """
    # Sanity check.
    if (len(objID) != config.LEN_ID):
        return RetVal(False, 'objID has invalid length', None)

    # Query the object.
    doc = database.dbHandles['CmdForce'].find_one({'objid': objID})
    if doc is None:
        return RetVal(False, 'Could not find <{}>'.format(objID), None)

    # Unpack the force.
    try:
        force = np.fromstring(doc['central_force'])
    except KeyError:
        force = np.zeros(3)

    # Unpack the torque.
    try:
        torque = np.fromstring(doc['torque'])
    except KeyError:
        torque = np.zeros(3)

    # Return the result.
    return RetVal(True, None, {'force': force, 'torque': torque})


@typecheck
def addTemplate(templateID: bytes, data: dict):
    """
    Store the template ``data`` under the name ``templateID``.

    This function does not care what ``data`` contains, as long as it can be
    serialised.

    :param bytes templateID: template name
    :param dict data: arbitrary template data.
    :return: Success
    """
    # Insert the document only if it does not exist already. The return
    # value contains the old document, ie. **None** if the document
    # did not yet exist.
    ret = database.dbHandles['Templates'].find_and_modify(
        {'templateID': templateID}, {'$setOnInsert': data}, upsert=True)

    if ret is None:
        # No template with name ``templateID`` exists yet --> success.
        return RetVal(True, None, templateID)
    else:
        # A template with name ``templateID`` already existed --> failure.
        msg = 'Template ID <{}> already exists'.format(templateID)
        return RetVal(False, msg, None)


@typecheck
def getRawTemplate(templateID: bytes):
    """
    Return the raw data in the database for ``templateID``.

    :param bytes templateID:
    :return dict: template data.
    """
    # Retrieve the template. Return immediately if it does not exist.
    doc = database.dbHandles['Templates'].find_one({'templateID': templateID})
    if doc is None:
        msg = 'Invalid template ID <{}>'.format(templateID)
        logit.info(msg)
        return RetVal(False, msg, None)
    else:
        return RetVal(True, None, doc)