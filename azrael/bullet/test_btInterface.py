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

import sys
import pytest
import cytoolz
import IPython
import numpy as np

import azrael.bullet.btInterface as btInterface
from azrael.util import int2id, id2int

ipshell = IPython.embed


def test_add_get_single():
    """
    Add an object to the SV database.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # Create an object ID for the test.
    id_0 = int2id(0)

    # The number of SV entries must now be zero.
    assert btInterface.count() == 0
    data, ok = btInterface.get(id_0)
    assert not ok

    # Query an object. Since none exist yet this must return with an error.
    data, ok = btInterface.get([id_0])
    assert not ok

    # Create an object and serialise it.
    data = btInterface.defaultData()
    data = btInterface.pack(data).tostring()

    # Add the object to the DB with ID=0.
    ok = btInterface.add(id_0, data, np.int64(1).tostring())
    assert ok

    # Query the object. This must return the SV data directly.
    out, ok = btInterface.get(id_0)
    assert ok
    assert out == data
    
    # Query the same object but supply it as a list. This must return a list
    # with one element which is the exact same object as before.
    out, ok = btInterface.get([id_0])
    assert ok
    assert len(out) == 1
    assert out[0] == data

    print('Test passed')


def test_add_get_multiple():
    """
    Add multiple objects to the DB.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # Create two object IDs for this test.
    id_0 = int2id(0)
    id_1 = int2id(1)

    # The number of SV entries must now be zero.
    assert btInterface.count() == 0
    data, ok = btInterface.get(id_0)
    assert not ok

    # Create an object and serialise it.
    data_0 = btInterface.defaultData()
    data_0.position[:] = 0
    data_0 = btInterface.pack(data_0).tostring()

    data_1 = btInterface.defaultData()
    data_1.position[:] = 10 * np.ones(3)
    data_1 = btInterface.pack(data_1).tostring()

    # Add the objects to the DB.
    ok = btInterface.add(id_0, data_0, np.int64(1).tostring())
    assert ok
    ok = btInterface.add(id_1, data_1, np.int64(1).tostring())
    assert ok

    # Query the objects individually.
    out, ok = btInterface.get(id_0)
    assert (out, ok) == (data_0, True)
    out, ok = btInterface.get(id_1)
    assert (out, ok) == (data_1, True)
    
    # Manually query multiple objects.
    out, ok = btInterface.get([id_0, id_1])
    assert ok
    assert len(out) == 2
    assert out[0] == data_0
    assert out[1] == data_1

    # Query all objects at once.
    out, ok = btInterface.getAll()
    assert ok
    assert len(out) == 2
    assert out[id_0] == data_0
    assert out[id_1] == data_1

    print('Test passed')


def test_add_same():
    """
    Try to add two objects with the same ID.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # Create one object ID for this test.
    id_0 = int2id(0)

    # The number of SV entries must now be zero.
    assert btInterface.count() == 0
    data, ok = btInterface.get(id_0)
    assert not ok

    # Create an object and serialise it.
    data_0 = btInterface.defaultData()
    data_0.position[:] = np.zeros(3)
    data_0 = btInterface.pack(data_0).tostring()

    data_1 = btInterface.defaultData()
    data_1.position[:] = 10 * np.ones(3)
    data_1 = btInterface.pack(data_1).tostring()

    # Add the objects to the DB.
    ok = btInterface.add(id_0, data_0, np.int64(1).tostring())
    assert ok

    # Add the same object with the same ID -- this should work because nothing
    # has changed.
    ok = btInterface.add(id_0, data_0, np.int64(1).tostring())
    assert ok

    # Add a different object with the same ID -- this should not work.
    ok = btInterface.add(id_0, data_1, np.int64(1).tostring())
    assert not ok

    print('Test passed')


def test_get_set_force():
    """
    Query and update the force vector for an object.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # Create two object IDs for this test.
    id_0 = int2id(0)
    id_1 = int2id(1)

    # Create an object and serialise it.
    data_0 = btInterface.defaultData()
    data_0.position[:] = 0
    data_0 = btInterface.pack(data_0).tostring()

    data_1 = btInterface.defaultData()
    data_1.position[:] = 10 * np.ones(3)
    data_1 = btInterface.pack(data_1).tostring()

    # Add the two objects to the DB.
    ok = btInterface.add(id_0, data_0, np.int64(1).tostring())
    assert ok
    ok = btInterface.add(id_1, data_1, np.int64(1).tostring())
    assert ok

    # Specify the forces and their position with respect to the center of mass.
    f0 = np.zeros(3, np.float64)
    f1 = np.zeros(3, np.float64)
    p0 = np.zeros(3, np.float64)
    p1 = np.zeros(3, np.float64)

    force, rel_pos, ok = btInterface.getForce(id_0)
    assert ok
    assert np.array_equal(force, f0)
    assert np.array_equal(rel_pos, p0)
    force, rel_pos, ok = btInterface.getForce(id_1)
    assert ok
    assert np.array_equal(force, f1)
    assert np.array_equal(rel_pos, p1)

    # Update the force vector of the second object.
    f1 = np.ones(3, np.float64)
    p1 = 2 * np.ones(3, np.float64)
    assert btInterface.setForce(id_1, f1, p1)

    # Only the force of the second object must have changed.
    force, rel_pos, ok = btInterface.getForce(id_0)
    assert ok
    assert np.array_equal(force, f0)
    assert np.array_equal(rel_pos, p0)
    force, rel_pos, ok = btInterface.getForce(id_1)
    assert ok
    assert np.array_equal(force, f1)
    assert np.array_equal(rel_pos, p1)

    print('Test passed')


def test_update_statevar():
    """
    Add an object to the SV database.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # Create an object ID for the test.
    id_0 = int2id(0)

    # Create an object and serialise it.
    data_0 = btInterface.defaultData()
    data_0 = btInterface.pack(data_0).tostring()

    # Add the object to the DB with ID=0.
    assert btInterface.add(id_0, data_0, np.int64(1).tostring())

    # Query the object. This must return the SV data directly.
    out, ok = btInterface.get(id_0)
    assert (out, ok) == (data_0, True)
    
    # Create an object and serialise it.
    data_1 = btInterface.defaultData()
    data_1.position[:] += 10
    data_1 = btInterface.pack(data_1).tostring()

    # Change the SV data and check it was updated correctly.
    assert btInterface.update(id_0, data_1)
    out, ok = btInterface.get(id_0)
    assert (out, ok) == (data_1, True)

    # Change the SV data and check it was updated correctly.
    assert not btInterface.update(int2id(10), data_1)

    print('Test passed')


def test_suggest_position():
    """
    Set and retrieve a position suggestion.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # Create an object ID for the test.
    id_0 = int2id(0)

    # Create an object and serialise it.
    data_0 = btInterface.defaultData()
    data_0 = btInterface.pack(data_0).tostring()

    # Query suggested position for non-existing object.
    data, ok = btInterface.getSuggestedPosition(id_0)
    assert not ok

    # Suggest a position for a non-existing object.
    p = np.array([1, 2, 5])
    assert not btInterface.setSuggestedPosition(int2id(10), p)

    # Add the object to the DB with ID=0.
    assert btInterface.add(id_0, data_0, np.int64(1).tostring())

    # Query suggested position for existing object. This must suceed. However,
    # since no position has been suggested yet the returned values must be
    # None.
    data, ok = btInterface.getSuggestedPosition(id_0)
    assert (data, ok) == (None, True)

    # Suggest a position for the just inserted object.
    p = np.array([1, 2, 5])
    assert btInterface.setSuggestedPosition(id_0, p)

    # Retrieve the suggested position.
    data, ok = btInterface.getSuggestedPosition(id_0)
    assert ok
    assert np.array_equal(data, p)

    # Void the suggested position.
    assert btInterface.setSuggestedPosition(id_0, None)
    data, ok = btInterface.getSuggestedPosition(id_0)
    assert (data, ok) == (None, True)
    
    print('Test passed')


def test_create_work_package_without_objects():
    """
    Create, fetch, and update Bullet work packages.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # The token to use.
    token = 1

    # This call is invalid because the IDs must be a non-empty list.
    wpid, ok = btInterface.createWorkPackage([], token, 1, 2)
    assert not ok

    # Valid function call. The first WPID must be 1.
    IDs = [int2id(_) for _ in range(3, 5)]
    wpid, ok = btInterface.createWorkPackage(IDs, token, 1, 2)
    assert (wpid, ok) == (1, True)

    # Valid function call. The second WPID must be 2.
    IDs = [int2id(_) for _ in range(3, 5)]
    _, ok = btInterface.createWorkPackage(IDs, token, 1, 2)
    assert (_, ok) == (2, True)
    del _

    # Retrieving a non-existing ID must fail.
    data, _, ok = btInterface.getWorkPackage(0)
    assert not ok
    
    # Retrieving an existing ID must succeed. In this case, it must also return
    # an empty list because there are no objects in the DB yet.
    data, admin, ok = btInterface.getWorkPackage(wpid)
    assert (data, ok) == ([], True)
    assert (admin.token, admin.dt, admin.maxsteps) == (token, 1, 2)
    
    # Update (and thus remove) a non-existing work package. The number of SV
    # data elements is irrelevant to this function.
    assert not btInterface.updateWorkPackage(0, token, {})
    
    # Update (and thus remove) an existing work package. Once again, the number
    # of SV data elements is irrelevant to the function.
    assert btInterface.updateWorkPackage(wpid, token, {})

    # Try to update it once more. This must now fail since it was just updated
    # (and the WP thus removed).
    assert not btInterface.updateWorkPackage(wpid, token, {})
    
    print('Test passed')


def test_create_work_package_with_objects():
    """
    Create, fetch, and update Bullet work packages.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # The token to use.
    token = 1

    # Create two objects.
    data_1 = btInterface.defaultData(imass=1)
    data_1 = btInterface.pack(data_1).tostring()

    data_2 = btInterface.defaultData(imass=2)
    data_2 = btInterface.pack(data_2).tostring()

    id_1, id_2 = int2id(1), int2id(2)
    assert btInterface.add(id_1, data_1, np.int64(1).tostring())
    assert btInterface.add(id_2, data_2, np.int64(1).tostring())

    # Valid function call. The first WPID must be 1.
    wpid_1, ok = btInterface.createWorkPackage([id_1], token, 1, 2)
    assert (wpid_1, ok) == (1, True)

    # Valid function call. The second WPID must be 2.
    wpid_2, ok = btInterface.createWorkPackage([id_1, id_2], token, 3, 4)
    assert (wpid_2, ok) == (2, True)

    # Retrieve the first work package.
    ret, admin, ok = btInterface.getWorkPackage(wpid_1)
    assert (len(ret), ok) == (1, True)
    assert (admin.token, admin.dt, admin.maxsteps) == (token, 1, 2)
    ret = ret[0]
    assert ret.id == id_1
    assert ret.sv == data_1
    assert np.array_equal(np.fromstring(ret.force), [0, 0, 0])
    
    # Retrieve the second work package.
    ret, admin, ok = btInterface.getWorkPackage(wpid_2)
    assert (admin.token, admin.dt, admin.maxsteps) == (token, 3, 4)
    assert (len(ret), ok) == (2, True)
    assert (ret[0].id, ret[1].id) == (id_1, id_2)
    assert (ret[0].sv, ret[1].sv) == (data_1, data_2)
    assert np.array_equal(np.fromstring(ret[0].force), [0, 0, 0])
    
    # Create a new data set to replace the old one.
    data_3 = btInterface.defaultData(imass=3)
    data_3 = btInterface.pack(data_3).tostring()

    # Manually retrieve the original data for id_1.
    assert btInterface.get(id_1) == (data_1, True)

    # Update the first work package with the wrong token. The call must fail
    # and the data must remain intact.
    assert not btInterface.updateWorkPackage(wpid_1, token + 1, {id_1: data_3})
    assert btInterface.get(id_1) == (data_1, True)
    
    # Update the first work package with the correct token. The data should now
    # have been updated.
    assert btInterface.updateWorkPackage(wpid_1, token, {id_1: data_3})
    assert btInterface.get(id_1) == (data_3, True)

    print('Test passed')
    

def test_get_set_forceandtorque():
    """
    Query and update the force- and torque vectors for an object.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # Create two object IDs for this test.
    id_0 = int2id(0)
    id_1 = int2id(1)

    # Create two objects and serialise them.
    data_0 = btInterface.defaultData()
    data_0.position[:] = 0
    data_0 = btInterface.pack(data_0).tostring()

    data_1 = btInterface.defaultData()
    data_1.position[:] = 10 * np.ones(3)
    data_1 = btInterface.pack(data_1).tostring()

    # Add the two objects to the DB.
    assert btInterface.add(id_0, data_0, np.int64(1).tostring())
    assert btInterface.add(id_1, data_1, np.int64(1).tostring())

    # Specify the forces and torques.
    f0 = np.zeros(3, np.float64)
    f1 = np.zeros(3, np.float64)
    t0 = np.zeros(3, np.float64)
    t1 = np.zeros(3, np.float64)

    ok, force, torque = btInterface.getForceAndTorque(id_0)
    assert ok
    assert np.array_equal(force, f0)
    assert np.array_equal(torque, t0)
    ok, force, torque = btInterface.getForceAndTorque(id_1)
    assert ok
    assert np.array_equal(force, f1)
    assert np.array_equal(torque, t1)

    # Update the force and torque vectors of the second object.
    f1 = np.ones(3, np.float64)
    t1 = 2 * np.ones(3, np.float64)
    assert btInterface.setForceAndTorque(id_1, f1, t1)

    # Only the force an torque of the second object must have changed.
    ok, force, torque = btInterface.getForceAndTorque(id_0)
    assert ok
    assert np.array_equal(force, f0)
    assert np.array_equal(torque, t0)
    ok, force, torque = btInterface.getForceAndTorque(id_1)
    assert ok
    assert np.array_equal(force, f1)
    assert np.array_equal(torque, t1)

    print('Test passed')


if __name__ == '__main__':
    test_get_set_forceandtorque()
    test_create_work_package_with_objects()
    test_create_work_package_without_objects()
    test_suggest_position()
    test_update_statevar()
    test_get_set_force()
    test_add_same()
    test_add_get_multiple()
    test_add_get_single()
