let socket = io.connect()
let session_id = parseInt(location.pathname.split('/')[2])

socket.emit('subscribe', {
    "session_id": session_id,
    "mode": "stats"
})

socket.on('stats', (message) => {
    let rows = JSON.parse(message)
    let html = "<table>"

    let build_row = (block, cols) => {
        let html = ""

        cols.forEach((col) => {
            html += "<" + block + ">" + col + "</" + block + ">"
        })

        return html
    }

    rows.forEach((row) => {
        html += "<tr>"

        let block = "td"
        if (row.type === 'header') {
            block = "th"
        }
        html += build_row(block, row.cols)
        html += "</tr>"
    })

    html += "</table>"

    document.getElementById("stats").innerHTML = html
})




