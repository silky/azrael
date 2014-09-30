var StateVariable = function(pos, vel, orientation, scale, imass) {
    var d = {'radius': scale,
         'scale': scale,
         'imass': imass,
         'restitution': 0.9,
         'orientation': orientation,
         'position': pos,
         'velocityLin': vel,
         'velocityRot': [0, 0, 0],
         'cshape': [0, 1, 1, 1]};
    return d
}

/*
  Create a ThreeJS geometry object.
*/
function compileMesh (p, scale) {
    var geo = new THREE.Geometry()

    console.log('Compiling mesh with ' + p.length + ' vertices');

    // Apply the scaling.
    for (ii=0; ii < p.length; ii ++) p[ii] *= scale;

    // Compile the geometry.
    for (ii=0; ii < p.length; ii += 9) {
        // Add the three vertex that define a triangle.
        var v1 = new THREE.Vector3(p[ii+0], p[ii+1], p[ii+2])
        var v2 = new THREE.Vector3(p[ii+3], p[ii+4], p[ii+5])
        var v3 = new THREE.Vector3(p[ii+6], p[ii+7], p[ii+8])
        geo.vertices.push(v1, v2, v3);

        // Define the current face in terms of the three just added
        // vertices.
        var facecnt = Math.floor(ii / 3)
        geo.faces.push( new THREE.Face3(facecnt, facecnt+1, facecnt+2))
    }

    // Assign random face colors.
    for (var i = 0; i < geo.faces.length; i++) {
        var face = geo.faces[i];
        face.color.setHex(Math.random() * 0xffffff);
    }

    return geo;
}

var getGeometryCube = function () {
    buf_vert = [
        -1.0, -1.0, -1.0,   -1.0, -1.0, +1.0,   -1.0, +1.0, +1.0,
        +1.0, +1.0, -1.0,   -1.0, -1.0, -1.0,   -1.0, +1.0, -1.0,
        +1.0, -1.0, +1.0,   -1.0, -1.0, -1.0,   +1.0, -1.0, -1.0,
        +1.0, +1.0, -1.0,   +1.0, -1.0, -1.0,   -1.0, -1.0, -1.0,
        -1.0, -1.0, -1.0,   -1.0, +1.0, +1.0,   -1.0, +1.0, -1.0,
        +1.0, -1.0, +1.0,   -1.0, -1.0, +1.0,   -1.0, -1.0, -1.0,
        -1.0, +1.0, +1.0,   -1.0, -1.0, +1.0,   +1.0, -1.0, +1.0,
        +1.0, +1.0, +1.0,   +1.0, -1.0, -1.0,   +1.0, +1.0, -1.0,
        +1.0, -1.0, -1.0,   +1.0, +1.0, +1.0,   +1.0, -1.0, +1.0,
        +1.0, +1.0, +1.0,   +1.0, +1.0, -1.0,   -1.0, +1.0, -1.0,
        +1.0, +1.0, +1.0,   -1.0, +1.0, -1.0,   -1.0, +1.0, +1.0,
        +1.0, +1.0, +1.0,   -1.0, +1.0, +1.0,   +1.0, -1.0, +1.0];

    for (ii=0; ii < buf_vert.length; ii++) {
        buf_vert[ii] *= 0.5;
    }
    return buf_vert;
}

/* ------------------------------------------------------------
   Commands to Clacks/Clerk
 ------------------------------------------------------------ */

function ping() {
    var cmd = JSON.stringify({'cmd': 'ping_clacks', 'payload': {}})
    var dec = function (msg) {
        return JSON.parse(msg.data)
    };
    return [cmd, dec]
}


function suggestPosition(objID, pos) {
    var cmd = JSON.stringify({'cmd': 'suggest_pos',
                              'payload': {'objID': objID, 'pos': pos}})
    var dec = function (msg) {
        return JSON.parse(msg.data)
    };
    return [cmd, dec]
}


function setID(objID) {
    var cmd = JSON.stringify({'cmd': 'set_id', 'payload': {'objID': objID}});
    var dec = function (msg) {
        var parsed = JSON.parse(msg.data)
        return {'ok': parsed.ok, 'objID': parsed.payload.objID}
    };
    return [cmd, dec]
}

function getTemplate(templateID) {
    var cmd = {'cmd': 'get_template', 'payload': {'templateID': templateID}}
    cmd = JSON.stringify(cmd)
    var dec = function (msg) {
        var parsed = JSON.parse(msg.data)
        return {'ok': parsed.ok,
                'geometry': parsed.payload.geo,
                'cs': parsed.payload.cs}
    };

    return [cmd, dec]
}

function addTemplate(templateID, cs, vertices) {
    var cmd = {'cmd': 'add_template', 'payload':
               {'name': templateID, 'cs': cs, 'geo': vertices,
                'boosters': [], 'factories': []}}
    cmd = JSON.stringify(cmd)
    var dec = function (msg) {
        var parsed = JSON.parse(msg.data)
        return {'ok': parsed.ok}
    };
    return [cmd, dec]
}

function spawn(templateID, pos, vel, orient, scale, imass) {
    var sv = StateVariable(pos, vel, orient, scale, imass)
    sv.cshape = [4, 1, 1, 1]

    var payload = {'name': null, 'templateID': templateID, 'sv': sv}
    var cmd = {'cmd': 'spawn', 'payload': payload}
    cmd = JSON.stringify(cmd)
    var dec = function (msg) {
        var parsed = JSON.parse(msg.data)
        return {'ok': parsed.ok, 'objID': parsed.payload.objID}
    };
    return [cmd, dec]
}

function getAllObjectIDs() {
    var cmd = {'cmd': 'get_all_objids', 'payload': {}}
    cmd = JSON.stringify(cmd)
    var dec = function (msg) {
        var parsed = JSON.parse(msg.data)
        return {'ok': parsed.ok, 'objIDs': parsed.payload.objIDs}
    };
    return [cmd, dec]
}

function getTemplateID(objID) {
    var cmd = {'cmd': 'get_template_id', 'payload': {'objID': objID}}
    cmd = JSON.stringify(cmd)
    var dec = function (msg) {
        var parsed = JSON.parse(msg.data)
        return {'ok': parsed.ok, 'templateID': parsed.payload.templateID}
    };
    return [cmd, dec]
}

function getStateVariable(objID) {
    var cmd = {'cmd': 'get_statevar', 'payload': {'objIDs': objID}}
    cmd = JSON.stringify(cmd)
    var dec = function (msg) {
        var parsed = JSON.parse(msg.data)
        return {'ok': parsed.ok, 'sv': parsed.payload.data}
    };
    return [cmd, dec]
}


function arrayEqual(arr1, arr2) {
    if (arr1.length != arr2.length) return false;
    var isequal = true
    for (var jj in arr1) {
        if (arr1[jj] != arr2[jj]) {
            isequal = false;
            break;
        }
    }
    return isequal;
}

/* ------------------------------------------------------------
   Command flow for one frame.
 ------------------------------------------------------------ */

function* mycoroutine(connection) {
    // Ensure we are live.
    var msg = yield ping()
    if (msg.ok == false) {console.log('Error'); return;}
    console.log('Ping successfull')

    // Request a new ID for the controller assigned to us.
    msg = yield setID(null)
    if (msg.ok == false) {console.log('Error'); return;}
    console.log('Controller ID: ' + msg.objID);

    // Define a new template.
    var buf_vert = getGeometryCube();
    var templateID = [111, 108, 105];
    var cs = [4, 1, 1, 1];
    msg = yield addTemplate(templateID, cs, buf_vert);
    console.log('Added player template')

    // Spawn the just defined template.
    msg = yield spawn(templateID, [0, 0, 0], [0, 0, 50], [0, 0, 0, 1], 1, 1)
    var playerID = msg.objID
    console.log('Spawned player object with objID=' + playerID);

    // ----------------------------------------------------------------------
    // Rendering.
    // ----------------------------------------------------------------------
    // Compute the Aspect Ratio.
    var AR = window.innerWidth/window.innerHeight
    var FOV = 45
    
    // Create scene and camera.
    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(FOV, AR, 0.1, 1000);
    
    camera.position.set( 0, 5, -10 );
    camera.lookAt(new THREE.Vector3(0, 0, 0))
    
    // Initialise the renderer and add it to the page.
    var renderer = new THREE.WebGLRenderer();
    renderer.setSize(window.innerWidth, window.innerHeight);
    document.body.appendChild(renderer.domElement);

    // Initialise the camera controller to emulate FPS navigation.
    controls = new THREE.FlyControls(camera);
    controls.movementSpeed = 25;
    controls.rollSpeed = 10 * Math.PI / 24;
    controls.autoForward = false;
    controls.dragToLook = false;
    controls.update(1)

    // Query the State variables of all objects and update their
    // position on screen.
    var obj_cache = {}
    while (true) {
        // Retrieve all object IDs.
        msg = yield getAllObjectIDs();
        if (msg.data == false) {console.log('Error'); return;}
        objIDs = msg.objIDs

        // Get the SV for all objects.
        msg = yield getStateVariable(objIDs)
        if (msg.ok == false) {console.log('Error'); return;}
        var allSVs = msg.sv

        // Update the position and orientation of all objects. Add objects if
        // they are not yet part of the scene.
        for (var ii in objIDs) {
            // Do not render ourselves.
            if (arrayEqual(playerID, objIDs[ii])) continue;

            if (obj_cache[objIDs[ii]] == undefined) {
                // Get SV for current object.
                var scale = allSVs[ii].sv.scale

                // Object not yet in local cache --> get its template ID and
                // then the template itself.
                msg = yield getTemplateID(objIDs[ii]);
                console.log('Added template ' + msg.templateID + ' to cache')
                msg = yield getTemplate(msg.templateID);
                if (msg.ok == false) {console.log('Error'); return;}
                var geo = compileMesh(msg.geometry, scale)

                // Build a new object in ThreeJS.
                var mat = new THREE.MeshBasicMaterial(
                    {vertexColors: THREE.FaceColors,
                     wireframe: false,
                     wireframeLinewidth: 3})
                var new_geo = new THREE.Mesh(geo, mat)

                // Add the object to the cache and scene.
                obj_cache[objIDs[ii]] = new_geo
                scene.add(new_geo);
            }

            // Update object position.
            var sv = allSVs[ii].sv
            obj_cache[objIDs[ii]].position.x = sv.position[0]
            obj_cache[objIDs[ii]].position.y = sv.position[1]
            obj_cache[objIDs[ii]].position.z = sv.position[2]

            // Update object orientation.
            var q = sv.orientation
            obj_cache[objIDs[ii]].quaternion.x = q[0]
            obj_cache[objIDs[ii]].quaternion.y = q[1]
            obj_cache[objIDs[ii]].quaternion.z = q[2]
            obj_cache[objIDs[ii]].quaternion.w = q[3]
        }

        // The myClick attribute is set in the mouse click handler but
        // processed here to keep everything inside the co-routine.
        // The following code block will move the player object to the
        // camera position.
        if (window.myClick == true) {
            // Extract camera position.
            var pos = [0, 0, 0]
            pos[0] = camera.position.x
            pos[1] = camera.position.y
            pos[2] = camera.position.z

            // Extract camera quaternion.
            var x = camera.quaternion.x
            var y = camera.quaternion.y
            var z = camera.quaternion.z
            var w = camera.quaternion.w

            // Obtain the view-direction of the camer. For this
            // purpose multiply the (0, 0, 1) position vector with the
            // camera Quaternion. The multiplication works via the
            // rotation matrix that corresponds to the Quaternion,
            // albeit I simplified it below since the first two
            // components of the (0, 0, 1) vector are zero anyway.
            var v1 = [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w]
            var v2 = [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w]
            var v3 = [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y]
            var view = [2*x*z + 2*y*w, 2*y*z - 2*x*w, 1 - 2*x*x - 2*y*y]
            var view_norm = Math.pow(view[0], 2) + Math.pow(view[1], 2)
            view_norm += Math.pow(view[2], 2)

            // Normalise the view vector.
            if (view_norm < 1e-6) {view = [0, 0, 0]}
            else {for (ii in view) view[ii] /= -Math.sqrt(view_norm)}

            // Put the newly spawned object a ahead of us.
            pos[0] += 2 * view[0]
            pos[1] += 2 * view[1]
            pos[2] += 2 * view[2]

            // Compute the initial velocity of the new object. It
            // moves in the view direction of the camera.
            for (ii in view) {view[ii] *= 0.2}

            // Spawn the new object at the correct position and with
            // the correct velocity and orientation.
            var templateID = [111, 108, 105];
            msg = yield spawn(templateID, pos, view, [x, y, z, w], 0.25, 20)

            // Mark the mouse event as processed.
            window.myClick = false
        }

        // Render the sence and update the camera position.
        renderer.render(scene, camera);
        controls.update(0.01)

        // Put the player object at the camera's position.
        var pos = [0, 0, 0]
        pos[0] = camera.position.x
        pos[1] = camera.position.y
        pos[2] = camera.position.z
        msg = yield suggestPosition(playerID, pos);
    }

    console.log('All done')
}

window.onload = function() {
    // Create a websocket connection.
    var connection = new WebSocket('ws://' + window.location.host + '/websocket');
    var protocol = mycoroutine(connection);

    // Error handler.
    connection.onerror = function(error) {
        console.log('Error detected: ' + error);
    }
    
    // Callback function that will handle the Websocket. This function
    // will be set in the message handler itself and is supplied by
    // the Clerk/Clacks command functions.
    this.decoder = undefined;

    // Initialise the clicked flag.
    window.myClick = false
    window.onclick = function (event) {window.myClick = true}

    // Define callback for WS on-open.
    connection.onopen = function() {
        console.log('Established Websocket Connection')

        // Start the co-routine. It will return with a command to send
        // to Clerk, as well as a function that can interpret the result.
        var next = protocol.next()

        // Store the call back function and send the command to Clacks.
        this.decoder = next.value[1]
        connection.send(next.value[0])
    }

    connection.onmessage = function(msg) {
        // Decode the message with the previously installed call back
        // and pass the result to the co-routine. This will return
        // yet another command plus a callback function that can
        // interpret the response.
        var next = protocol.next(this.decoder(msg))
        if (next.done == true) {
            console.log('Finished')
            return
        }

        // Store the callback and dispatch the command.
        this.decoder = next.value[1]
        connection.send(next.value[0])
    }
}