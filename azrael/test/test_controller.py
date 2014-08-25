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
Test the controller base class.

The controller class is merely a convenience class to wrap the Clerk
commands. As such the tests here merely test these wrappers. See `test_clerk`
if you want to see thorough tests for the Clerk functionality.
"""

# Name of Echo controller (for convenience).
echo_ctrl = 'Echo'.encode('utf8')

import sys
import time
import pytest
import IPython
import subprocess
import numpy as np

import azrael.clerk
import azrael.clacks
import azrael.wscontroller
import azrael.controller
import azrael.parts as parts
import azrael.protocol as protocol
import azrael.config as config
import azrael.bullet.btInterface as btInterface

from azrael.util import int2id, id2int

ipshell = IPython.embed
WSControllerBase = azrael.wscontroller.WSControllerBase
ControllerBase = azrael.controller.ControllerBase


def killall():
    subprocess.call(['pkill', 'killme'])


def startAzrael(ctrl_type):
    """
    Start all Azrael services and return their handles.
    
    ``ctrl_type`` may be  either 'ZeroMQ' or 'Websocket'. The only
    difference this makes is that the 'Websocket' version will also
    start a Clacks server, whereas for 'ZeroMQ' the respective handle
    will be **None**.

    :param str ctrl_type: the controller type ('ZeroMQ' or 'Websocket').
    :return: handles to (clerk, ctrl, clacks)
    """
    killall()
    
    # Start Clerk and instantiate Controller.
    clerk = azrael.clerk.Clerk(reset=True)
    clerk.start()

    if ctrl_type == 'ZeroMQ':
        # Instantiate the ZeroMQ version of the Controller.
        ctrl = ControllerBase()
        ctrl.setupZMQ()
        ctrl.connectToClerk()

        # Do not start a Clacks process.
        clacks = None
    elif ctrl_type == 'Websocket':
        # Start a Clacks process.
        clacks = azrael.clacks.ClacksServer()
        clacks.start()

        # Instantiate the Websocket version of the Controller.
        ctrl = WSControllerBase('ws://127.0.0.1:8080/websocket', 1)
        assert ctrl.ping()
    else:
        print('Unknown controller type <{}>'.format(ctrl_type))
        assert False
    return clerk, ctrl, clacks


def stopAzrael(clerk, clacks):
    """
    Kill all processes related to Azrael.

    :param clerk: handle to Clerk process.
    :param clacks: handle to Clacks process.
    """
    # Terminate the Clerk.
    clerk.terminate()
    clerk.join(timeout=3)

    # Terminate the Clacks (if one was started).
    if clacks is not None:
        clacks.terminate()
        clacks.join(timeout=3)

    # Forcefully terminate everything.
    killall()


def test_ping():
    """
    Send a ping to the Clerk and check the response is correct.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael('ZeroMQ')

    ok, ret = ctrl.ping()
    assert (ok, ret) == (True, 'pong clerk'.encode('utf8'))

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


@pytest.mark.parametrize('ctrl_type', ['Websocket', 'ZeroMQ'])
def test_spawn_one_controller(ctrl_type):
    """
    Ask Clerk to spawn one (echo) controller.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael(ctrl_type)

    # Instruct Clerk to spawn a Controller named 'Echo'. The call will return
    # the ID of the controller which must be '2' ('0' is invalid and '1' was
    # already given to the controller in the WS handler).
    templateID = '_templateNone'.encode('utf8')
    ok, ctrl_id = ctrl.spawn(echo_ctrl, templateID, np.zeros(3))
    assert (ok, ctrl_id) == (True, int2id(2))

    # Spawn another template but this time without also createing a new
    # controller process to control the object. We cannot explicitly verify
    # that not controller process was created but we can verify that the spawn
    # command itself worked.
    templateID = '_templateNone'.encode('utf8')
    ok, ctrl_id = ctrl.spawn(None, templateID, np.zeros(3))
    assert (ok, ctrl_id) == (True, int2id(3))

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


@pytest.mark.parametrize('ctrl_type', ['Websocket', 'ZeroMQ'])
def test_spawn_and_talk_to_one_controller(ctrl_type):
    """
    Ask Clerk to spawn one (echo) controller. Then send a message to that
    controller to ensure everything works.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael(ctrl_type)

    # Instruct Clerk to spawn a Controller named 'Echo'. The call will return
    # the ID of the controller which must be '2' ('0' is invalid and '1' was
    # already given to the Controller).
    templateID = '_templateNone'.encode('utf8')
    ok, ctrl_id = ctrl.spawn(echo_ctrl, templateID, np.zeros(3))
    assert (ok, ctrl_id) == (True, int2id(2))

    # Send a message to `ctrl_id`.
    msg_orig = 'test'.encode('utf8')
    ok, ret = ctrl.sendMessage(ctrl_id, msg_orig)
    assert ok

    # Fetch the response. Poll for it a few times because it may not arrive
    # immediately.
    for ii in range(5):
        ok, data = ctrl.recvMessage()
        assert isinstance(ok, bool)
        if ok:
            src, msg_ret = data
        else:
            src, msg_ret = None, None

        if ok and (src is not None):
            break
        time.sleep(0.1)
    assert src is not None

    # The source must be the newly created process and the response must be the
    # original messages prefixed with the controller ID.
    assert src == ctrl_id
    if (ctrl_id + msg_orig) != msg_ret:
        print(ok, src, msg_ret)
    assert ctrl_id + msg_orig == msg_ret

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


@pytest.mark.parametrize('ctrl_type', ['Websocket', 'ZeroMQ'])
def test_spawn_and_get_state_variables(ctrl_type):
    """
    Spawn a new Controller and query its state variables.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael(ctrl_type)

    # Instruct Clerk to spawn a Controller named 'Echo'. The call will return
    # the ID of the controller which must be '2' ('0' is invalid and '1' was
    # already given to the controller in the WS handler).
    templateID = '_templateNone'.encode('utf8')
    ok, id0 = ctrl.spawn(echo_ctrl, templateID, pos=np.ones(3), vel=-np.ones(3))
    assert (ok, id0) == (True, int2id(2))

    ok, sv = ctrl.getStateVariables(id0)
    assert (ok, len(sv)) == (True, 1)
    assert id0 in sv

    # Set the suggested position.
    ok, ret = ctrl.suggestPosition(id0, np.ones(3))
    assert ok

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


@pytest.mark.parametrize('ctrl_type', ['Websocket', 'ZeroMQ'])
def test_multi_controller(ctrl_type):
    """
    Start a few echo Controllers processes. Then manually operate one
    Controller instance to bounce messages off the other controllers.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael(ctrl_type)

    # Launch the Controllers (default implementation is an echo).
    num_proc = 10
    proc = [ControllerBase() for _ in range(num_proc)]
    for p in proc:
        p.start()

    # Send a random message to all Controllers (the Clerk object should have
    # assigned them the numbers [0, num_proc-1])
    err = None
    try:
        # The message.
        t = 'test'.encode('utf8')

        # Compile list of object IDs. The list starts with ID 2 because ID=0 is
        # invalid and ID=1 was already given to the 'ctrl' controller,
        obj_ids = [int2id(_) for _ in range(2, num_proc + 2)]

        # Send the test message to every controller. Every controller gets a
        # distinct one because it contains the ID of the target controller.
        for dst in obj_ids:
            assert ctrl.sendMessage(dst, t + dst)

        # Every echo controller should return the same message prefixed with
        # its own ID.
        for ii in range(num_proc):
            ok, (src, msg) = ctrl.recvMessage()
            while len(msg) == 0:
                time.sleep(.02)
                ok, (src, msg) = ctrl.recvMessage()
            # Start/end of message must both contain the dst ID.
            assert msg[:config.LEN_ID] == msg[-config.LEN_ID:]
    except AssertionError as e:
        err = e

    # Terminate controller processes.
    for p in proc:
        p.terminate()
        p.join()

    if err is not None:
        raise err

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


@pytest.mark.parametrize('ctrl_type', ['Websocket', 'ZeroMQ'])
def test_getAllObjectIDs(ctrl_type):
    """
    Ensure the getAllObjectIDs command reaches Clerk.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael(ctrl_type)
    
    # Parameters and constants for this test.
    objID_2 = int2id(2)
    templateID = '_templateNone'.encode('utf8')

    # So far no objects have been spawned.
    ok, ret = ctrl.getAllObjectIDs()
    assert (ok, ret) == (True, [])

    # Spawn a new object.
    templateID = '_templateNone'.encode('utf8')
    ok, ret = ctrl.spawn(echo_ctrl, templateID, np.zeros(3))
    assert (ok, ret) == (True, objID_2)

    # The object list must now contain the ID of the just spawned object.
    ok, ret = ctrl.getAllObjectIDs()
    assert (ok, ret) == (True, [objID_2])

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


@pytest.mark.parametrize('ctrl_type', ['Websocket', 'ZeroMQ'])
def test_get_template(ctrl_type):
    """
    Spawn some objects from the default templates and query their template IDs.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael(ctrl_type)

    # Parameters and constants for this test.
    id_0, id_1 = int2id(2), int2id(3)
    templateID_0 = '_templateNone'.encode('utf8')
    templateID_1 = '_templateCube'.encode('utf8')
    
    # Spawn a new object. It must have ID=2 because ID=1 was already given to
    # the controller.
    ok, ctrl_id = ctrl.spawn(echo_ctrl, templateID_0, np.zeros(3))
    assert (ok, ctrl_id) == (True, id_0)

    # Spawn another object from a different template.
    ok, ctrl_id = ctrl.spawn(echo_ctrl, templateID_1, np.zeros(3))
    assert (ok, ctrl_id) == (True, id_1)

    # Retrieve template of first object.
    ok, ret = ctrl.getTemplateID(id_0)
    assert (ok, ret) == (True, templateID_0)
    
    # Retrieve template of second object.
    ok, ret = ctrl.getTemplateID(id_1)
    assert (ok, ret) == (True, templateID_1)
    
    # Attempt to retrieve a non-existing object.
    ok, ret = ctrl.getTemplateID(int2id(100))
    assert not ok

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')
    

@pytest.mark.parametrize('ctrl_type', ['Websocket', 'ZeroMQ'])
def test_create_fetch_template(ctrl_type):
    """
    Add a new object to the templateID DB and query it again.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael(ctrl_type)

    # Request an invalid ID.
    ok, ret = ctrl.getTemplate('blah'.encode('utf8'))
    assert not ok

    # Clerk has a few default objects. This one has no collision shape...
    ok, ret = ctrl.getTemplate('_templateNone'.encode('utf8'))
    assert ok
    assert np.array_equal(ret.cs, [0, 1, 1, 1])
    assert len(ret.geo) == len(ret.boosters) == len(ret.factories) == 0

    # ... this one is a sphere...
    ok, ret = ctrl.getTemplate('_templateSphere'.encode('utf8'))
    assert ok
    assert np.array_equal(ret.cs, [3, 1, 1, 1])
    assert len(ret.geo) == len(ret.boosters) == len(ret.factories) == 0

    # ... and this one is a cube.
    ok, ret = ctrl.getTemplate('_templateCube'.encode('utf8'))
    assert ok
    assert np.array_equal(ret.cs, [4, 1, 1, 1])
    assert len(ret.geo) == len(ret.boosters) == len(ret.factories) == 0

    # Add a new object template.
    cs = np.array([1, 2, 3, 4], np.float64)
    geo = np.array([5, 6, 7, 8], np.float64)
    templateID = 't1'.encode('utf8')
    ok, templateID = ctrl.addTemplate(templateID, cs, geo, [], [])

    # Fetch the just added template again.
    ok, ret = ctrl.getTemplate(templateID)
    assert np.array_equal(ret.cs, cs)
    assert np.array_equal(ret.geo, geo)
    assert len(ret.boosters) == len(ret.factories) == 0

    # Define a new object with two boosters and one factory unit.
    # The 'boosters' and 'factories' arguments are a list of named
    # tuples. Their first argument is the unit ID (Azrael does not
    # automatically assign any).
    cs = np.array([1, 2, 3, 4], np.float64)
    geo = np.array([5, 6, 7, 8], np.float64)
    b0 = parts.booster(0, pos=np.zeros(3), orient=[0, 0, 1], max_force=0.5)
    b1 = parts.booster(1, pos=np.zeros(3), orient=[0, 0, 1], max_force=0.5)
    f0 = parts.factory(0, pos=np.zeros(3), orient=[0, 0, 1], speed=[0.1, 0.5])

    # Add the new template.
    templateID = 't2'.encode('utf8')
    ok, templateID = ctrl.addTemplate(templateID, cs, geo, [b0, b1], [f0])

    # Retrieve the geometry of the just created object and verify it is correct.
    ok, ret = ctrl.getGeometry(templateID)
    assert np.array_equal(ret, geo)

    # Retrieve the entire template and verify the CS and geometry.
    ok, ret = ctrl.getTemplate(templateID)
    assert np.array_equal(ret.cs, cs)
    assert np.array_equal(ret.geo, geo)

    # The template must also feature two boosters and one factory.
    assert len(ret.boosters) == 2
    assert len(ret.factories) == 1

    # Explicitly verify the booster- and factory units. The easiest (albeit
    # not most readable) way to do the comparison is to convert the unit
    # descriptions (which are named tuples) to byte strings and compare those.
    out_boosters = [parts.booster_tostring(_) for _ in ret.boosters]
    out_factories = [parts.factory_tostring(_) for _ in ret.factories]
    assert parts.booster_tostring(b0) in out_boosters
    assert parts.booster_tostring(b1) in out_boosters
    assert parts.factory_tostring(f0) in out_factories

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


if __name__ == '__main__':
    test_create_fetch_template('ZeroMQ')
    test_get_template('ZeroMQ')
    test_getAllObjectIDs('ZeroMQ')
    test_ping()
    test_spawn_one_controller('ZeroMQ')
    test_spawn_and_talk_to_one_controller('ZeroMQ')
    test_spawn_and_get_state_variables('ZeroMQ')
    test_multi_controller('ZeroMQ')
