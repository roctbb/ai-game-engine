function GeSdk() {
    this.socket = io.connect()
    this.session_id = parseInt(location.pathname.split('/')[2])

    this.socket.emit('subscribe', {
        "session_id": this.session_id
    })

    this.socket.on('frame', (message) => {
        let frame = JSON.parse(message)
        if (this.on_frame) {
            this.on_frame(frame)
        }
    })
}

GeSdk.prototype.subscribe_to_frame = function (frame_callback) {
    this.on_frame = frame_callback
}




