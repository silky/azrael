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
Physics manager.
"""
import sys
import zmq
import time
import pika
import IPython
import logging
import setproctitle
import multiprocessing
import numpy as np

import azrael.util as util
import azrael.config as config
import azrael.bullet.cython_bullet
import azrael.bullet.btInterface as btInterface
import azrael.bullet.bullet_data as bullet_data

from azrael.typecheck import typecheck

ipshell = IPython.embed


@typecheck
def sweeping(data: list, labels: np.ndarray, dim: str):
    """
    Return sets of overlapping AABBs in the dimension ``dim``.

    This function implements the 'Sweeping' algorithm to determine which sets
    of AABBs overlap.

    Sweeping is straightforward: sort all start/stop positions and determine
    the overlapping sets.

    The returned sets does not contain the elements of data, but their
    corresponding label from the list of ``labels``.

    :param list data: list of dictionaries which must contain ['aabb']
    :param np.int64 labels: integer array to label the elements in data.
    :param str dim: the axis to check (must be one of ['x', 'y', 'z'])
    """
    assert len(labels) == len(data)

    # Convenience.
    N = 2 * len(data)

    # Pre-allocate arrays for start/stop position, objID, and an
    # increment/decrement array used for convenient processing afterwards.
    arr_pos = np.zeros(N, np.float64)
    arr_lab = np.zeros(N, np.int64)
    arr_inc = np.zeros(N, np.int8)

    # Fill the arrays.
    for ii in range(len(data)):
        arr_pos[2 * ii: 2 * ii + 2] = np.array(data[ii][dim])
        arr_lab[2 * ii: 2 * ii + 2] = labels[ii]
        arr_inc[2 * ii: 2 * ii + 2] = [+1, -1]

    # Sort all three arrays according to the start/stop positions.
    idx = np.argsort(arr_pos)
    arr_lab = arr_lab[idx]
    arr_inc = arr_inc[idx]

    # Output array.
    out = []

    # Sweep over the sorted data and compile the list of object sets.
    sumVal = 0
    setObjs = set()
    for (inc, objID) in zip(arr_inc, arr_lab):
        # Update the index variable and add the current object to the set.
        sumVal += inc
        setObjs.add(objID)

        # A new set of overlapping AABBs is complete whenever `sumVal`
        # reaches zero.
        if sumVal == 0:
            out.append(setObjs)
            setObjs = set()

        # Safety check: this must never happen.
        assert sumVal >= 0
    return out


@typecheck
def computeCollisionSetsAABB(IDs: list, SVs: list):
    """
    Return potential collision sets among all ``IDs`` and associated ``SVs``.

    :param IDs: list of object IDs.
    :param SVs: list of object BulletData instances. Corresponds to IDs.
    """
    # Sanity check.
    if len(IDs) != len(SVs):
        return False, None

    # Fetch all AABBs.
    ok, aabbs = btInterface.getAABB(IDs)
    if not ok:
        return False, None

    # The 'sweeping' function requires a list of dictionaries. Each dictionary
    # must contain the min/max spatial extend in x/y/z direction.
    data = []
    for objID, sv, aabb in zip(IDs, SVs, aabbs):
        pos = sv.position
        x0, x1 = pos[0] - aabb, pos[0] + aabb
        y0, y1 = pos[1] - aabb, pos[1] + aabb
        z0, z1 = pos[2] - aabb, pos[2] + aabb

        data.append({'x': [x0, x1], 'y': [y0, y1], 'z': [z0, z1]})

    # Enumerate the objects.
    labels = np.arange(len(IDs))

    # Determine the overlapping objects in 'x' di
    stage_0 = sweeping(data, labels, 'x')

    # Analyse every subset of the previous output further.
    stage_1 = []
    for subset in stage_0:
        tmpData = [data[_] for _ in subset]
        tmpLabels = np.array(tuple(subset), np.int64)
        stage_1.extend(sweeping(tmpData, tmpLabels, 'y'))

    # Analyse every subset of the previous output further.
    stage_2 = []
    for subset in stage_1:
        tmpData = [data[_] for _ in subset]
        tmpLabels = np.array(tuple(subset), np.int64)
        stage_2.extend(sweeping(tmpData, tmpLabels, 'z'))

    # Convert the labels back to object IDs.
    out = [[IDs[_] for _ in __] for __ in stage_2]
    return True, out


class LeonardBase(multiprocessing.Process):
    """
    Base class for Physics manager.

    No physics is actually computed here. The class serves mostly as an
    interface for the actual Leonard implementations, as well as a test
    framework.
    """
    def __init__(self):
        super().__init__()

        # Create a Class-specific logger.
        name = '.'.join([__name__, self.__class__.__name__])
        self.logit = logging.getLogger(name)
        self.logit.debug('mydebug')
        self.logit.info('myinfo')

    def setup(self):
        """
        Stub for initialisation code that cannot go into the constructor.

        Since Leonard is a process not everything can be initialised in the
        constructor because it executes before the process forks.
        """
        pass

    @typecheck
    def step(self, dt: (int, float), maxsteps: int):
        """
        Advance the simulation by ``dt`` using at most ``maxsteps``.

        This method will use a primitive Euler step to update the state
        variables. This suffices as a proof of concept.

        :param float dt: time step in seconds.
        :param int maxsteps: maximum number of sub-steps to simulate for one
                             ``dt`` update.
        """
        # Retrieve the SV for all objects.
        ok, all_ids = btInterface.getAllObjectIDs()
        ok, all_sv = btInterface.getStateVariables(all_ids)

        # Iterate over all objects and update their SV information in Bullet.
        for objID, sv in zip(all_ids, all_sv):
            # Fetch the force vector for the current object from the DB.
            ok, force, torque = btInterface.getForceAndTorque(objID)
            if not ok:
                continue

            # Update velocity and position.
            sv.velocityLin[:] += force * 0.001
            sv.position[:] += dt * sv.velocityLin

            # See if there is a suggested position available for this
            # object. If so, use it.
            ok, tmp = btInterface.getSuggestedPosition(objID)
            if ok:
                # Apply the specified values.
                if tmp.pos is not None:
                    sv.position[:] = tmp.pos
                if tmp.vel is not None:
                    sv.velocityLin[:] = tmp.vel
                if tmp.orient is not None:
                    sv.orientation[:] = tmp.orient
                # Clear the DB entry (they would otherwise be applied
                # at every frame).
                btInterface.setSuggestedPosition(objID, None)

            # Serialise the state variables and update them in the DB.
            btInterface.update(objID, sv)

    def run(self):
        """
        Drive the periodic physics updates.
        """
        setproctitle.setproctitle('killme Leonard')

        # Initialisation.
        self.setup()
        self.logit.debug('Setup complete.')

        # Reset the database.
        btInterface.initSVDB(reset=False)

        # Trigger the `step` method every 10ms, if possible.
        t0 = time.time()
        while True:
            # Wait, if less than 10ms have passed, or proceed immediately.
            sleep_time = 0.01 - (time.time() - t0)
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Backup the time stamp.
            t0 = time.time()

            # Trigger the physics update step.
            with util.Timeit('step') as timeit:
                self.step(0.1, 10)


class LeonardBulletMonolithic(LeonardBase):
    """
    An extension of ``LeonardBase`` that uses Bullet for the physics.

    Unlike ``LeonardBase`` this class actually *does* update the physics.
    """
    def __init__(self):
        super().__init__()
        self.bullet = None

    def setup(self):
        # Instantiate the Bullet engine. The (1, 0) parameters mean
        # the engine has ID '1' and does not build explicit pair caches.
        self.bullet = azrael.bullet.cython_bullet.PyBulletPhys(1, 0)

    @typecheck
    def step(self, dt, maxsteps):
        """
        Advance the simulation by ``dt`` using at most ``maxsteps``.

        This method will query all SV objects from the database and updates
        them in the Bullet engine. Then it defers to Bullet for the physics
        update.  Finally it copies the updated values in Bullet back to the
        database.

        :param float dt: time step in seconds.
        :param int maxsteps: maximum number of sub-steps to simulate for one
                             ``dt`` update.
        """

        # Retrieve the SV for all objects.
        ok, allSV = btInterface.getAllStateVariables()

        # Iterate over all objects and update them.
        for objID, sv in allSV.items():
            # See if there is a suggested position available for this
            # object. If so, use it.
            ok, sug_pos = btInterface.getSuggestedPosition(objID)
            if ok and sug_pos is not None:
                # Assign the position and delete the suggestion.
                sv.position[:] = sug_pos
                btInterface.setSuggestedPosition(objID, None)

            # Convert the objID to an integer.
            btID = util.id2int(objID)

            # Pass the SV data from the DB to Bullet.
            self.bullet.setObjectData([btID], sv)

            # Retrieve the force vector and tell Bullet to apply it.
            ok, force, torque = btInterface.getForceAndTorque(objID)
            if ok:
                self.bullet.applyForceAndTorque(btID, 0.01 * force, torque)

        # Wait for Bullet to advance the simulation by one step.
        IDs = [util.id2int(_) for _ in allSV.keys()]
        with util.Timeit('compute') as timeit:
            self.bullet.compute(IDs, dt, maxsteps)

        # Retrieve all objects from Bullet and write them back to the database.
        for objID, sv in allSV.items():
            ok, sv = self.bullet.getObjectData([util.id2int(objID)])
            if ok == 0:
                # Restore the original cshape because Bullet will always
                # return zeros here.
                sv.cshape[:] = allSV[objID].cshape[:]
                btInterface.update(objID, sv)


class LeonardBulletSweeping(LeonardBulletMonolithic):
    """
    Compute physics on independent collision sets.

    This is a modified version of ``LeonardBulletMonolithic`` that uses
    Sweeping to compile the collision sets and then updates the physics for
    each set independently.

    This class is single threaded and uses a single Bullet instance to
    sequentially update the physics for each collision set.
    """
    @typecheck
    def step(self, dt, maxsteps):
        """
        Advance the simulation by ``dt`` using at most ``maxsteps``.

        This method will query all SV objects from the database and updates
        them in the Bullet engine. Then it defers to Bullet for the physics
        update.  Finally it copies the updated values in Bullet back to the
        database.

        :param float dt: time step in seconds.
        :param int maxsteps: maximum number of sub-steps to simulate for one
                             ``dt`` update.
        """

        # Retrieve the SV for all objects.
        ok, allSV = btInterface.getAllStateVariables()

        # Compile a dedicated list of IDs and their SVs for the collision
        # detection algorithm.
        IDs = list(allSV.keys())
        sv = [allSV[_] for _ in IDs]

        # Compute the collision sets.
        with util.Timeit('CCS') as timeit:
            ok, res = computeCollisionSetsAABB(IDs, sv)
        assert ok

        # Log the number of created collision sets.
        util.logMetricQty('#CollSets', len(res))

        # Process all subsets individually.
        for subset in res:
            # Compile the subset dictionary for the current collision set.
            coll_SV = {_: allSV[_] for _ in subset}

            # Iterate over all objects and update them.
            for objID, sv in coll_SV.items():
                # See if there is a suggested position available for this
                # object. If so, use it.
                ok, sug_pos = btInterface.getSuggestedPosition(objID)
                if ok and sug_pos is not None:
                    # Assign the position and delete the suggestion.
                    sv.position[:] = sug_pos
                    btInterface.setSuggestedPosition(objID, None)

                # Convert the objID to an integer.
                btID = util.id2int(objID)

                # Pass the SV data from the DB to Bullet.
                self.bullet.setObjectData([btID], sv)

                # Retrieve the force vector and tell Bullet to apply it.
                ok, force, torque = btInterface.getForceAndTorque(objID)
                if ok:
                    self.bullet.applyForceAndTorque(btID, 0.01 * force, torque)

            # Wait for Bullet to advance the simulation by one step.
            IDs = [util.id2int(_) for _ in coll_SV.keys()]
            with util.Timeit('compute') as timeit:
                self.bullet.compute(IDs, dt, maxsteps)

            # Retrieve all objects from Bullet and write them back to the
            # database.
            for objID, sv in coll_SV.items():
                ok, sv = self.bullet.getObjectData([util.id2int(objID)])
                if ok == 0:
                    # Restore the original cshape because Bullet will always
                    # return zeros here.
                    sv.cshape[:] = coll_SV[objID].cshape[:]
                    btInterface.update(objID, sv)


class LeonardBulletSweepingMultiST(LeonardBulletMonolithic):
    """
    Compute physics on independent collision sets with multiple engines.

    This is a modified version of ``LeonardBulletMonolithic`` and similar to
    LeonardBulletSweeping but employes work packages and multiple engines.

    This class is single threaded. All Bullet engines run sequentially in the
    main thread. The work packages are distributed at random to the engines.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = 0

    def setup(self):
        # Instantiate several Bullet engine. The (1, 0) parameters mean
        # the engine has ID '1' and does not build explicit pair caches.
        engine = azrael.bullet.cython_bullet.PyBulletPhys
        self.bulletEngines = [engine(_ + 1, 0) for _ in range(5)]

    @typecheck
    def step(self, dt, maxsteps):
        """
        Advance the simulation by ``dt`` using at most ``maxsteps``.

        This method will query all SV objects from the database and updates
        them in the Bullet engine. Then it defers to Bullet for the physics
        update.  Finally it copies the updated values in Bullet back to the
        database.

        :param float dt: time step in seconds.
        :param int maxsteps: maximum number of sub-steps to simulate for one
                             ``dt`` update.
        """

        # Retrieve the SV for all objects.
        ok, allSV = btInterface.getAllStateVariables()

        # Compile a dedicated list of IDs and their SVs for the collision
        # detection algorithm.
        IDs = list(allSV.keys())
        sv = [allSV[_] for _ in IDs]

        # Compute the collision sets.
        with util.Timeit('CCS') as timeit:
            ok, res = computeCollisionSetsAABB(IDs, sv)
        assert ok

        # Log the number of created collision sets.
        util.logMetricQty('#CollSets', len(res))

        # Convenience.
        cwp = btInterface.createWorkPackage

        # Update the token value for this iteration.
        self.token += 1

        all_wpids = []
        # Process all subsets individually.
        for subset in res:
            # Compile the subset dictionary for the current collision set.
            coll_SV = {_: allSV[_] for _ in subset}

            # Upload the work package into the DB.
            ok, wpid = cwp(list(subset), self.token, dt, maxsteps)

            # Keep track of the WPID.
            all_wpids.append(wpid)

        # Process each WP individually.
        for wpid in all_wpids:
            self.processWorkPackage(wpid)

        self.waitUntilWorkpackagesComplete(all_wpids, self.token)

    def waitUntilWorkpackagesComplete(self, all_wpids, token):
        """
        Block until all work packages have been completed.
        """
        while btInterface.countWorkPackages(token)[1] > 0:
            time.sleep(0.001)

    @typecheck
    def processWorkPackage(self, wpid: int):
        """
        Update the physics for all objects in ``wpid``.

        The Bullet engine is picked at random.

        :param int wpid: work package ID.
        """
        ok, worklist, admin = btInterface.getWorkPackage(wpid)
        assert ok

        # Pick an engine at random.
        engineIdx = int(np.random.randint(len(self.bulletEngines)))
        engine = self.bulletEngines[engineIdx]

        # Log the number of created collision sets.
        util.logMetricQty('Engine_{}'.format(engineIdx), len(worklist))

        # Iterate over all objects and update them.
        for obj in worklist:
            sv = obj.sv
            # Use the suggested position if we got one.
            if obj.sugPos is not None:
                sv.position[:] = np.fromstring(obj.sugPos)

            # Update the object in Bullet.
            btID = util.id2int(obj.id)
            engine.setObjectData([btID], sv)

            # Retrieve the force vector and tell Bullet to apply it.
            force = np.fromstring(obj.central_force)
            torque = np.fromstring(obj.torque)
            engine.applyForceAndTorque(btID, 0.01 * force, torque)

        # Tell Bullet to advance the simulation for all objects in the
        # current work list.
        IDs = [util.id2int(_.id) for _ in worklist]
        engine.compute(IDs, admin.dt, admin.maxsteps)

        # Retrieve the objects from Bullet again and update them in the DB.
        out = {}
        for obj in worklist:
            ok, sv = engine.getObjectData([util.id2int(obj.id)])
            if ok != 0:
                # Something went wrong. Reuse the old SV.
                sv = obj.sv
                self.logit.error('Unable to get all objects from Bullet')

            # Restore the original cshape because Bullet will always return
            # zeros here.
            sv.cshape[:] = obj.sv.cshape[:]
            out[obj.id] = sv

        # Update the data and delete the WP.
        ok = btInterface.updateWorkPackage(wpid, admin.token, out)
        if not ok:
            msg = 'Failed to update work package {}'.format(wpid)
            self.logit.warning(msg)


class LeonardBulletSweepingMultiMT(LeonardBulletSweepingMultiST):
    """
    Compute physics on independent collision sets with multiple engines.

    Leverage LeonardBulletSweepingMultiST but process the work packages in
    dedicated Worker processes.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workers = []

    def __del__(self):
        """
        Kill all worker processes.
        """
        for worker in self.workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()

    def setup(self):
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.PUSH)
        self.sock.bind(config.addr_leonard_pushpull)

        # Spawn the workers.
        cls = LeonardBulletSweepingMultiMTWorker
        for ii in range(5):
            self.workers.append(cls(ii + 1))
            self.workers[-1].start()
        self.logit.info('Setup complete')

    def processWorkPackage(self, wpid: int):
        """
        Ensure "someone" processes the work package with ID ``wpid``.

        This method will usually be overloaded in sub-classes to actually send
        the WPs to a Bullet engine or worker processes.

        :param int wpid: work package ID to process.
        """
        self.sock.send(np.int64(wpid).tostring())


class LeonardBulletSweepingMultiMTWorker(multiprocessing.Process):
    """
    Distributed Physics Engine based on collision sets and work packages.

    The distribution of Work Packages happens via ZeroMQ push/pull sockets.
    """
    def __init__(self, workerID):
        super().__init__()
        self.workerID = workerID

        # Create a Class-specific logger.
        name = '.'.join([__name__, self.__class__.__name__])
        self.logit = logging.getLogger(name)

    @typecheck
    def run(self):
        """
        Update the physics for all objects in ``wpid``.

        :param int wpid: work package ID.
        """
        try:
            # Rename process to make it easy to find and kill them in the
            # process table.
            setproctitle.setproctitle('killme LeonardWorker')

            # Instantiate a Bullet engine.
            engine = azrael.bullet.cython_bullet.PyBulletPhys
            self.bullet = engine(self.workerID, 0)

            # Setup ZeroMQ.
            ctx = zmq.Context()
            sock = ctx.socket(zmq.PULL)
            sock.connect(config.addr_leonard_pushpull)
            self.logit.info('Worker {} connected'.format(self.workerID))

            # Process work packages as they arrive.
            while True:
                wpid = sock.recv()
                wpid = np.fromstring(wpid, np.int64)
                self.processWorkPackage(int(wpid))
        except KeyboardInterrupt:
            print('Worker {} quit'.format(self.workerID))

    def processWorkPackage(self, wpid: int):
        ok, worklist, admin = btInterface.getWorkPackage(wpid)
        assert ok

        # Log the number of collision sets to process.
        util.logMetricQty('Engine_{}'.format(self.workerID), len(worklist))

        # Iterate over all objects and update them.
        for obj in worklist:
            sv = obj.sv
            # Use the suggested position if we got one.
            if obj.sugPos is not None:
                sv.position[:] = np.fromstring(obj.sugPos)

            # Update the object in Bullet.
            btID = util.id2int(obj.id)
            self.bullet.setObjectData([btID], sv)

            # Retrieve the force vector and tell Bullet to apply it.
            force = np.fromstring(obj.central_force)
            torque = np.fromstring(obj.torque)
            self.bullet.applyForceAndTorque(btID, 0.01 * force, torque)

        # Tell Bullet to advance the simulation for all objects in the
        # current work list.
        IDs = [util.id2int(_.id) for _ in worklist]
        self.bullet.compute(IDs, admin.dt, admin.maxsteps)

        # Retrieve the objects from Bullet again and update them in the DB.
        out = {}
        for obj in worklist:
            ok, sv = self.bullet.getObjectData([util.id2int(obj.id)])
            if ok != 0:
                # Something went wrong. Reuse the old SV.
                sv = obj.sv
                self.logit.error('Unable to get all objects from Bullet')

            # Restore the original cshape because Bullet will always return
            # zeros here.
            sv.cshape[:] = obj.sv.cshape[:]
            out[obj.id] = sv

        # Update the data and delete the WP.
        ok = btInterface.updateWorkPackage(wpid, admin.token, out)
        if not ok:
            msg = 'Failed to update work package {}'.format(wpid)
            self.logit.warning(msg)


class LeonardBaseWorkpackages(LeonardBase):
    """
    A variation of ``LeonardBase`` that uses Work Packages.

    This class is a test dummy and should not be used in production. Like
    ``LeonardBase`` it does not actually compute any physics. It only creates
    work packages and does some dummy processing for them. Everything runs in
    the same process.

    A work package contains a sub-set of all objects in the simulation and a
    token. While this class segments the world, worker nodes will retrieve the
    work packages one by one and step the simulation for the objects inside
    those work packages.
    """
    def __init__(self):
        super().__init__()
        self.token = 0

    @typecheck
    def step(self, dt: (int, float), maxsteps: int):
        """
        Advance the simulation by ``dt`` using at most ``maxsteps``.

        :param float dt: time step in seconds.
        :param int maxsteps: maximum number of sub-steps to simulate for one
                             ``dt`` update.
        """

        # Retrieve the SV for all objects.
        ok, allSV = btInterface.getAllStateVariables()

        # --------------------------------------------------------------------
        # Create a single work list containing all objects and a new token.
        # --------------------------------------------------------------------
        IDs = list(allSV.keys())
        self.token += 1
        ok, wpid = btInterface.createWorkPackage(IDs, self.token, dt, maxsteps)
        if not ok:
            return

        # --------------------------------------------------------------------
        # Process the work list.
        # --------------------------------------------------------------------
        # Fetch the work list.
        ok, worklist, admin = btInterface.getWorkPackage(wpid)
        if not ok:
            return

        # Process the objects one by one. The `out` dict will hold the updated
        # SV information.
        out = {}
        for obj in worklist:
            # Retrieve the force vector.
            force = np.fromstring(obj.central_force)

            # Update the velocity and position.
            sv = obj.sv
            sv.velocityLin[:] += force * 0.001
            sv.position[:] += dt * sv.velocityLin

            # See if there is a suggested position available for this
            # object. If so, use it because the next call to updateWorkPackage
            # will void it.
            if obj.sugPos is not None:
                sv.position[:] = np.fromstring(obj.sugPos)

            # Add the new SV data to the output dictionary.
            out[obj.id] = sv

        # --------------------------------------------------------------------
        # Update the work list and mark it as completed.
        # --------------------------------------------------------------------
        btInterface.updateWorkPackage(wpid, admin.token, out)


class LeonardBaseWPRMQ(LeonardBase):
    """
    A variation of ``LeonardWorkpackages`` with RabbitMQ and work packages.

    This class is a test dummy and should not be used in production.

    This class is tailor made to test

    * RabbitMQ communication between Leonard and a separate Worker process
    * work packages.

    To this end it spawns a single ``LeonardRMQWorker`` and wraps each
    object into a dedicated work package.
    """
    @typecheck
    def __init__(self, num_workers: int=1, clsWorker=None):
        super().__init__()

        # Current token.
        self.token = 0
        self.workers = []
        self.num_workers = num_workers
        self.used_workers = set()

        if clsWorker is None:
            self.clsWorker = LeonardRMQWorker
        else:
            self.clsWorker = clsWorker

        # Create a Class-specific logger.
        name = '.'.join([__name__, self.__class__.__name__])
        self.logit = logging.getLogger(name)

    def __del__(self):
        """
        Kill all worker processes.
        """
        for worker in self.workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()

    def setup(self):
        """
        Setup RabbitMQ and spawn the worker processes.
        """
        # Create a RabbitMQ exchange.
        param = pika.ConnectionParameters(host=config.rabbitMQ_host)
        self.rmqconn = pika.BlockingConnection(param)
        del param

        # Create the channel.
        self.rmq = self.rmqconn.channel()

        # Delete the queues if they already exist.
        try:
            self.rmq.queue_delete(queue=config.rmq_wp)
        except pika.exceptions.ChannelClosed as err:
            pass
        try:
            self.rmq.queue_delete(queue=config.rmq_ack)
        except pika.exceptions.ChannelClosed as err:
            pass

        # Declare the queues and give RabbitMQ some time to setup.
        self.rmq.queue_declare(queue=config.rmq_wp, durable=False)
        self.rmq.queue_declare(queue=config.rmq_ack, durable=False)
        time.sleep(0.2)

        # Spawn the workers.
        for ii in range(self.num_workers):
            self.workers.append(self.clsWorker(ii + 1))
            self.workers[-1].start()
        self.logit.debug('Setup complete.')

    @typecheck
    def announceWorkpackage(self, wpid: int):
        """
        Announce the new work package with ID ``wpid``.

        :param int wpid: work package ID.
        """
        self.rmq.basic_publish(
            exchange='', routing_key=config.rmq_wp, body=util.int2id(wpid))

    @typecheck
    def step(self, dt: (int, float), maxsteps: int):
        """
        Advance the simulation by ``dt`` using at most ``maxsteps``.

        :param float dt: time step in seconds.
        :param int maxsteps: maximum number of sub-steps to simulate for one
                             ``dt`` update.
        """
        # Retrieve the SV for all objects.
        ok, allSV = btInterface.getAllStateVariables()
        IDs = list(allSV.keys())

        # Update the token value for this iteration.
        self.token += 1

        # Create one work package for every object. This is inefficient but
        # useful as a test to ensure nothing breaks when there are many work
        # packages available at the same time.
        all_wpids = set()
        cwp = btInterface.createWorkPackage
        for cur_id in IDs:
            # Upload the work package into the DB.
            ok, wpid = cwp([cur_id], self.token, dt, maxsteps)
            if not ok:
                continue

            # Announce the new WP and track its ID.
            self.announceWorkpackage(wpid)
            all_wpids.add(wpid)
            del cur_id, wpid, ok
        del IDs, allSV

        # Wait until all work packages have been processed.
        self.waitUntilWorkpackagesComplete(all_wpids)

    @typecheck
    def waitUntilWorkpackagesComplete(self, all_wpids: set):
        """
        Wait until ``all_wpids`` have been acknowledged.

        :param set all_wpids: set of all work packages.
        """
        self.used_workers.clear()

        def callback(ch, method, properties, body):
            # Unpack the IDs of the WP and worker.
            wpid, workerid = body[:config.LEN_ID], body[config.LEN_ID:]
            wpid = util.id2int(wpid)

            # Remove the WP from the set. The set will not contain the ID if
            # another worker has finished first with the same WP. Furthermore,
            # add the WorkerID to 'used_workers' for testing purposes.
            if wpid in all_wpids:
                all_wpids.discard(wpid)
                self.used_workers.add(int(np.fromstring(workerid, dtype=int)))

            # Acknowledge message receipt to RabbitMQ server.
            ch.basic_ack(delivery_tag=method.delivery_tag)

            # Quit the event loop when all WPs have been processed.
            if len(all_wpids) == 0:
                ch.stop_consuming()

        # Start Pika event loop to consume all messages in the ACK channel.
        self.rmq.basic_consume(callback, queue=config.rmq_ack)
        self.rmq.start_consuming()


class LeonardRMQWorker(multiprocessing.Process):
    """
    A dedicated worker process attached to RabbitMQ.

    This worker runs independently of any Leonard process, possibly even on a
    different machine.

    .. note::
       Like ``LeonardBase`` this worker does not actually compute any
       physics. It just implements the framework for testing.
    """
    @typecheck
    def __init__(self, worker_id: int):
        super().__init__()

        # ID of this worker. Keep both the integer and binary version handy.
        self.id = np.int64(worker_id)
        self.id_binary = self.id.tostring()

        # Create a Class-specific logger.
        name = '.'.join([__name__, self.__class__.__name__])
        self.logit = logging.getLogger(name)

    @typecheck
    def advanceSimulation(self, wpid: int):
        """
        Retrieve the work package and process all objects in it.

        This function does not actually compute any physics on the objects. It
        just retrieves the work package and queries all objects specified
        therein.

        :param int wpid: work package ID to fetch and process.
        """
        # Convert work package ID to integer and fetch the work list.
        ok, worklist, admin = btInterface.getWorkPackage(wpid)
        if not ok:
            return

        # Process the objects one by one. The `out` dict will contain the
        # SV data after Bullet updated it.
        out = {}
        for obj in worklist:
            # Retrieve the force vector.
            force = np.fromstring(obj.central_force)

            # Update the velocity and position.
            sv = obj.sv
            sv.velocityLin[:] += force * 0.001
            sv.position[:] += admin.dt * sv.velocityLin

            # Update the object position if one was explicitly provided because
            # `updateWorkPackage` will void it later.
            if obj.sugPos is not None:
                sv.position[:] = np.fromstring(obj.sugPos)

            # Add the processed SV into the output dictionary.
            out[obj.id] = sv

        # --------------------------------------------------------------------
        # Mark the WP as completed and delete it.
        # --------------------------------------------------------------------
        btInterface.updateWorkPackage(wpid, admin.token, out)

    def setup(self):
        """
        Stub for initialisation code that cannot go into the constructor.

        Since Leonard is a process not everything can be initialised in the
        constructor because it executes before the process forks.
        """
        pass

    def run(self):
        """
        Start the RabbitMQ event loop and wait for work packages.

        Leonard will dispatched its work packages via RabbitMQ and this method
        will pick them up and process them.
        """
        setproctitle.setproctitle('killme LeonardWorker')

        # Perform any pending initialisation.
        self.setup()

        # Connect to RabbitMQ exchange.
        param = pika.ConnectionParameters(host=config.rabbitMQ_host)
        self.rmqconn = pika.BlockingConnection(param)
        del param

        # Create (or attach to) a named channel. The name is 'config.ex_msg'.
        self.rmq = self.rmqconn.channel()
        self.rmq.queue_declare(queue=config.rmq_wp, durable=False)
        self.rmq.queue_declare(queue=config.rmq_ack, durable=False)

        # Ensure workers do not pre-fetch additional message to implement load
        # balancing instead of a round-robin or greedy message retrieval.
        #self.rmq.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            """
            Callback for when RabbitMQ receives a message.
            """
            # Unpack the work package ID and update the physics.
            wpid = util.id2int(body)
            self.advanceSimulation(wpid)

            # Acknowledge message receipt and tell Leonard which worker
            # finished which work package.
            ch.basic_ack(delivery_tag=method.delivery_tag)
            ch.basic_publish(exchange='', routing_key=config.rmq_ack,
                             body=util.int2id(wpid) + self.id_binary)

        # Install the callback and start the event loop. start_consuming will
        # not return.
        self.rmq.basic_consume(callback, queue=config.rmq_wp)
        self.rmq.start_consuming()


class LeonardRMQWorkerBullet(LeonardRMQWorker):
    """
    Extend ``LeonardRMQWorker`` with Bullet physics.
    """
    def __init__(self, *args):
        super().__init__(*args)

        # The Bullet engine will not be instantiated until this worker runs in
        # its own process. This avoids data duplication during the fork.
        self.bullet = None

        # Create a Class-specific logger.
        self.logit = logging.getLogger(
            __name__ + '.' + self.__class__.__name__)

    def setup(self):
        # Instantiate Bullet engine.
        self.bullet = azrael.bullet.cython_bullet.PyBulletPhys(self.id, 0)

    def advanceSimulation(self, wpid):
        # Fetch the work package.
        ok, worklist, admin = btInterface.getWorkPackage(wpid)
        if not ok:
            return

        # Download the information into Bullet.
        for obj in worklist:
            sv = obj.sv
            # Use the suggested position if we got one.
            if obj.sugPos is not None:
                sv.position[:] = np.fromstring(obj.sugPos)

            # Update the object in Bullet.
            btID = util.id2int(obj.id)
            self.bullet.setObjectData([btID], sv)

            # Retrieve the force vector and tell Bullet to apply it.
            force = np.fromstring(obj.central_force)
            torque = np.fromstring(obj.torque)
            self.bullet.applyForceAndTorque(btID, 0.01 * force, torque)

        # Tell Bullet to advance the simulation for all objects in the current
        # work list.
        IDs = [util.id2int(_.id) for _ in worklist]
        self.bullet.compute(IDs, admin.dt, admin.maxsteps)

        # Retrieve the objects from Bullet again and update them in the DB.
        out = {}
        for obj in worklist:
            ok, sv = self.bullet.getObjectData([util.id2int(obj.id)])
            if ok != 0:
                # Something went wrong. Reuse the old SV.
                sv = obj.sv
                self.logit.error('Could not retrieve all objects from Bullet')

            # Restore the original cshape because Bullet will always return
            # zeros here.
            sv.cshape[:] = obj.sv.cshape[:]
            out[obj.id] = sv

        # Update the data and delete the WP.
        ok = btInterface.updateWorkPackage(wpid, admin.token, out)
        if not ok:
            self.logit.warning('Failed to update work package {}'.format(wpid))
