import sys
import time
import pytest
import IPython
import subprocess
import azrael.vectorgrid as vectorgrid
import numpy as np

ipshell = IPython.embed


def test_set_get_single_invalid():
    """
    Call the set/get functions with invalid parameters and ensure they fail.
    """
    # Test parameters.
    vg = vectorgrid
    pos = np.array([1, 2, 3], np.float64)
    value = np.array([-1, 0, 1], np.float64)

    # Delete all grids used in this test.
    assert vg.deleteAllGrids().ok

    # Attempt to get the value from a non-existing grid.
    ret = vg.getValues('force', [pos])
    assert not ret.ok
    assert 'unknown grid' in ret.msg.lower()
    assert ret.data is None
    assert ret == vg.setValues('force', [(pos, value)])

    # Invalid arguments to 'getValue'.
    assert not vg.getValues('force', [np.array([1, 2])]).ok

    # Invalid arguments to 'setValue'.
    assert not vg.setValues('force', [(np.array([1, 2]), value)]).ok
    assert not vg.setValues('force', [(pos, np.array([1, 2]))]).ok
    assert not vg.setValues('force', [(pos, np.array([1, 2, 3, 4]))]).ok

    print('Test passed')


def test_set_get_single():
    """
    Define a new grid type and set/get some values.
    """
    # Test parameters.
    vg = vectorgrid
    pos = np.array([1, 2, 3], np.float64)
    value = np.array([-1, 0, 1], np.float64)
    name = 'force'

    # Delete all grids used in this test.
    assert vg.deleteAllGrids().ok

    # Attempt to set/get values of an undefined grid.
    assert not vg.getValues(name, [pos]).ok

    # Attempt to set the value of a non-existing grid.
    assert not vg.setValues(name, [(pos, value)]).ok

    # Define a new grid. Its name is "force", it consists of 3-element vectors,
    # and has a spatial granularity of 1m in each dimension.
    assert vg.defineGrid(name=name, vecDim=3, granularity=1).ok

    # Query a value. This must return a zero vector (3 elements) because this
    # is the default value of the grid.
    ret = vg.getValues(name, [pos])
    assert ret.ok
    assert np.array_equal(ret.data, [np.zeros(3, np.float64)])

    # Repeat at a different position.
    ret = vg.getValues(name, [pos + np.pi])
    assert ret.ok
    assert np.array_equal(ret.data, [np.zeros(3, np.float64)])

    # Update the value and query it once more.
    assert vg.setValues(name, [(pos, value)]).ok
    ret = vg.getValues(name, [pos])
    assert ret.ok
    assert np.array_equal(ret.data, [value])

    print('Test passed')


def test_set_get_bulk():
    """
    Define a new grid type and set/get some values in bulk.
    """
    # Test parameters.
    vg = vectorgrid
    pos_0 = np.array([-1, 2, -3], np.float64)
    pos_1 = np.array([4, -5, 6], np.float64)
    val_0 = np.array([-1, 0, 1], np.float64)
    val_1 = np.array([-2, 1, 2], np.float64)
    name = 'force'

    # Delete all grids used in this test.
    assert vg.deleteAllGrids().ok

    # Attempt to set/get values of an undefined grid.
    assert not vg.getValues(name, [pos_0]).ok
    assert not vg.setValues(name, [(pos_0, val_0)]).ok

    # Define a new grid. Its name is "force", it consists of 3-element vectors,
    # and has a spatial granularity of 1m in each dimension.
    assert vg.defineGrid(name=name, vecDim=3, granularity=1).ok

    # Attempt to pass empty lists to set/get.
    assert not vg.getValues(name, []).ok
    assert not vg.setValues(name, []).ok

    # Query a value. This must return a zero vector (3 elements) because this
    # is the default value of the grid.
    ret = vg.getValues(name, [pos_0, pos_1])
    assert ret.ok and len(ret.data) == 2
    assert np.array_equal(ret.data[0], np.zeros(3, np.float64))
    assert np.array_equal(ret.data[1], np.zeros(3, np.float64))

    # Repeat at a different position.
    ret = vg.getValues(name, [pos_0 + np.pi, pos_1 + np.pi])
    assert ret.ok and len(ret.data) == 2
    assert np.array_equal(ret.data[0], np.zeros(3, np.float64))
    assert np.array_equal(ret.data[1], np.zeros(3, np.float64))

    # Update the value and query it once more.
    assert vg.setValues(name, [(pos_0, val_0), (pos_1, val_1)]).ok
    ret = vg.getValues(name, [pos_0, pos_1])
    assert ret.ok and len(ret.data) == 2
    assert np.array_equal(ret.data[0], val_0)
    assert np.array_equal(ret.data[1], val_1)

    print('Test passed')


def test_define_reset_delete_grid():
    """
    Define a new grid, add/set a value, delete the grid, and ensure it cannot
    be accessed anymore.
    """
    # Test parameters.
    vg = vectorgrid
    pos = np.array([1, 2, 3], np.float64)
    value = np.array([-1, 0, 1], np.float64)
    name = 'force'

    # Delete all grids used in this test.
    assert vg.deleteAllGrids().ok

    # Attempt to access the undefined grid.
    assert not vg.getValues(name, [pos]).ok
    assert not vg.setValues(name, [(pos, value)]).ok

    # Define a new grid.
    assert vg.defineGrid(name=name, vecDim=3, granularity=1).ok

    # Query default value.
    ret = vg.getValues(name, [pos])
    assert ret.ok and np.array_equal(ret.data, [np.zeros(3)])

    # Update the value at 'pos'.
    assert vg.setValues(name, [(pos, value)]).ok
    assert np.array_equal(vg.getValues(name, [pos]).data, [value])

    # Reset the grid and query 'pos' again.
    assert vg.resetGrid(name).ok
    assert np.array_equal(vg.getValues(name, [pos]).data, [np.zeros(3)])

    # Delete the grid and ensure it has become inaccessible.
    assert vg.getValues(name, [pos]).ok
    assert vg.setValues(name, [(pos, value)]).ok
    assert vg.deleteGrid(name).ok
    assert not vg.getValues(name, [pos]).ok
    assert not vg.setValues(name, [(pos, value)]).ok

    print('Test passed')


def test_define_reset_delete_grid_invalid():
    """
    Test invalid calling signatures.
    """
    # Test parameters.
    vg = vectorgrid
    pos = np.array([1, 2, 3], np.float64)
    value = np.array([-1, 0, 1], np.float64)
    name = 'force'

    # Delete all grids used in this test.
    assert vg.deleteAllGrids().ok

    # Attempt to reset a non-existing grid.
    ret = vg.resetGrid('blah')
    assert not ret.ok
    assert 'unknown grid' in ret.msg.lower()

    # Attempt to delete a non-existing grid.
    ret = vg.deleteGrid('blah')
    assert not ret.ok
    assert 'unknown grid' in ret.msg.lower()

    # Attempt to define a grid with non-positive granularity.
    assert not vg.defineGrid(name=name, vecDim=3, granularity=-1).ok
    assert not vg.defineGrid(name=name, vecDim=3, granularity=0).ok

    # Attempt to define a grid with invalid vecDim value.
    assert not vg.defineGrid(name=name, vecDim=-1, granularity=1).ok
    assert not vg.defineGrid(name=name, vecDim=0, granularity=1).ok

    # Attempt to define the same grid twice.
    assert vg.defineGrid(name=name, vecDim=3, granularity=1).ok
    ret = vg.defineGrid(name=name, vecDim=3, granularity=1)
    assert not ret.ok
    assert 'already exists' in ret.msg.lower()

    print('Test passed')


def test_set_get_region():
    """
    Set/get multiple values at once.
    """
    # Test parameters.
    vg = vectorgrid
    vecDim = 3
    name = 'force'

    # Delete all grids used in this test.
    assert vg.deleteAllGrids().ok

    # Define a new grid.
    assert vg.defineGrid(name=name, vecDim=vecDim, granularity=1).ok

    # Region offset in 3D space (these can be floating point numbers because
    # they denote actual positions, not grid indexes).
    ofs = np.array([1, 2.2, -3.3], np.float64)

    # Size of the region.
    regionDim = np.array([2, 4, 6], np.int64)

    # Data dimensionality (3 spatial dimensions plus the actual data
    # vector/value).
    dataDim = np.hstack((regionDim, vecDim))

    # Query an entire region.
    ret = vg.getRegion(name, ofs, regionDim)
    assert ret.ok
    assert np.array_equal(ret.data, np.zeros(dataDim, np.float64))

    # Create the data set for an `vecDim` vector field. For instance, an EM
    # field is a 3D vector field (ie vecDim=3), ie every position (x,y,z) has
    # an associated (E_x, E_y, E_z) vector.
    data = np.zeros(dataDim, np.float64)
    val = 0
    for x in range(regionDim[0]):
        for y in range(regionDim[1]):
            for z in range(regionDim[2]):
                data[x, y, z, :] = [val, val + 1, val + 2]
                val += 3
    del val, x, y, z

    # Apply the data set.
    ret = vg.setRegion(name, ofs, data)
    assert ret.ok

    # Query the entire region.
    ret = vg.getRegion(name, ofs, regionDim)
    assert np.array_equal(ret.data, data)

    # Query all points individually.
    for x in range(regionDim[0]):
        for y in range(regionDim[1]):
            for z in range(regionDim[2]):
                pos = ofs + np.array([x, y, z], np.float64)

                # Query one value with 'getValue'.
                ret = vg.getValues(name, [pos])
                assert ret.ok
                assert np.array_equal(ret.data, [data[x, y, z]])

                # Query one value with 'getRegion'.
                ret = vg.getRegion(name, np.array(pos), (1, 1, 1))
                assert ret.ok
                assert ret.data.shape == (1, 1, 1, vecDim)
                assert np.array_equal(ret.data[0, 0, 0], data[x, y, z])

    # Query other subsets.
    ret = vg.getRegion(name, ofs, regionDim - 1)
    assert ret.ok
    assert np.array_equal(ret.data.shape[:3], regionDim - 1)
    assert np.array_equal(ret.data, data[:-1, :-1, :-1])

    ret = vg.getRegion(name, ofs + 1, regionDim - 1)
    assert ret.ok
    assert np.array_equal(ret.data.shape[:3], regionDim - 1)
    assert np.array_equal(ret.data, data[1:, 1:, 1:])

    print('Test passed')


def test_deleteAll():
    """
    Define a few grids and delete them all at once with 'deleteAll'.
    """
    # Test parameters.
    vg = vectorgrid

    # Remove any pending grids.
    assert vg.deleteAllGrids().ok

    # No grids must exist.
    ret = vg.getAllGridNames()
    assert ret.ok
    assert ret.data == tuple()

    # The 'deleteAllGrids' function must succeed (even though it will not
    # delete any grids because none have been defined yet).
    assert vg.deleteAllGrids().ok

    # Define one grid and delete it with 'deleteAllGrids'.
    assert vg.defineGrid('grid_1', 3, 1).ok
    assert vg.getAllGridNames().data == ('grid_1', )
    assert vg.deleteAllGrids().ok
    assert vg.getAllGridNames().data == tuple()

    # Define two grids and delete both with 'deleteAllGrids'.
    assert vg.defineGrid('grid_1', 3, 1).ok
    assert vg.defineGrid('grid_2', 3, 1).ok
    assert set(vg.getAllGridNames().data) == set(['grid_1', 'grid_2'])
    assert vg.deleteAllGrids().ok
    assert vg.getAllGridNames().data == tuple()

    print('Test passed')


def test_granularity():
    """
    Use a grid with granularity that is not 1.
    """
    # Test parameters.
    vg = vectorgrid
    pos = np.array([1, 2, 3], np.float64)
    value = np.array([-1, 0, 1], np.float64)
    gran = 0.5
    vecDim = 3
    name = 'force'

    # Delete all grids used in this test.
    assert vg.deleteAllGrids().ok

    # Define a new grid.
    assert vg.defineGrid(name=name, vecDim=vecDim, granularity=gran).ok

    # Query default value at 'pos'.
    ret = vg.getValues(name, [pos])
    assert ret.ok and np.array_equal(ret.data, [np.zeros(vecDim)])

    # Update the value at 'pos'.
    assert vg.setValues(name, [(pos, value)]).ok
    assert np.array_equal(vg.getValues(name, [pos]).data, [value])

    # Query it again at 'pos'.
    ret = vg.getValues(name, [pos])
    assert ret.ok and np.array_equal(ret.data, [value])

    # Now query the values near pos. Internally, the vectorgrid engine will use
    # integer truncation (not rounding) to determine which vector element to
    # actually retrieve.
    ret = vg.getValues(name, [pos + gran / 2])
    assert ret.ok and np.array_equal(ret.data, [value])

    ret = vg.getValues(name, [pos + gran])
    assert ret.ok and np.array_equal(ret.data, [np.zeros(vecDim)])

    ret = vg.getValues(name, [pos - 0.1])
    assert ret.ok and np.array_equal(ret.data, [np.zeros(vecDim)])

    print('Test passed')


def test_auto_delete():
    """
    Ensure that vectorgrid automatically removes zero values.
    """
    # Test parameters.
    vg = vectorgrid
    pos = np.array([1, 2, 3], np.float64)
    value = np.array([-1, 0, 1], np.float64)
    vecDim = 3
    name = 'force'

    # Delete all grids used in this test.
    assert vg.deleteAllGrids().ok

    # Define a new grid.
    assert vg.defineGrid(name=name, vecDim=vecDim, granularity=1).ok

    # Initially only the admin element must be present.
    assert vg._DB_Grid[name].count() == 1

    # Add an element and ensure the document count increased to 2.
    assert vg.setValues(name, [(pos, value)]).ok
    assert vg._DB_Grid[name].count() == 2

    # Update the value to zero. This must decrease the count to 1 again.
    assert vg.setValues(name, [(pos, 0 * value)]).ok
    assert vg._DB_Grid[name].count() == 1

    # Repeat this experiment but with the bulk version 'setValues'.
    assert vg.setValues(name, [(pos, value)]).ok
    assert vg._DB_Grid[name].count() == 2
    assert vg.setValues(name, [(pos, 0 * value)]).ok
    assert vg._DB_Grid[name].count() == 1

    print('Test passed')


if __name__ == '__main__':
    test_set_get_bulk()
    test_auto_delete()
    test_deleteAll()
    test_define_reset_delete_grid()
    test_define_reset_delete_grid_invalid()
    test_set_get_single()
    test_set_get_single_invalid()
    test_set_get_region()
    test_granularity()
