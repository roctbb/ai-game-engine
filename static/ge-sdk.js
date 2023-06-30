function GeSdk() {
    this.socket = io.connect()
    this.session_id = parseInt(location.pathname.split('/')[2])
    this.replay = {
        frames: [],
        step: 0
    }

    this.socket.emit('subscribe', {
        "session_id": this.session_id
    })

    this.socket.on('frame', (message) => {
        let frame = JSON.parse(message)
        if (this.on_frame) {
            this.on_frame(frame)
        }
    })

    this.__replay_step = () => {
        if (this.on_frame) {
            this.on_frame(this.replay.frames[this.replay.step].frame)
        }

        this.replay.step += 1

        if (this.replay.step < this.replay.frames.length) {
            let current_frame_time = this.replay.frames[this.replay.step].time
            let previous_frame_time = this.replay.frames[this.replay.step - 1].time
            let span = current_frame_time - previous_frame_time
            setTimeout(this.__replay_step, span * 500)
        }
    }

    this.socket.on('replay', (message) => {
        let messages = JSON.parse(message)
        messages.forEach((message) => {
            if (message.type === 'frame') {
                this.replay.frames.push({
                    time: message.elapsed,
                    frame: message.data
                })
            }
        })

        this.__replay_step()
    })
}

GeSdk.prototype.subscribe_to_frame = function (frame_callback) {
    this.on_frame = frame_callback
}




