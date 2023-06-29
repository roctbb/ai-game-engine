function get_session_id() {
    let url_parts = location.pathname.split('/')
    let session_id = parseInt(url_parts[2])

    return session_id
}

let on_frame = undefined

function subscribe_to_frame(frame_callback) {
    on_frame = frame_callback
}

let socket = io.connect();

socket.emit('subscribe', {
    "session_id": get_session_id()
})

socket.on('frame', function (message) {
    let frame = JSON.parse(message)

    if (on_frame) {
        on_frame(frame)
    }
})

