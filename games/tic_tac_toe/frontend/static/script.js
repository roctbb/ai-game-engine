let sdk = new GeSdk()

function writePlayer1(name) {
    document.getElementById('player1').innerText = name
}

function writePlayer2(name) {
    document.getElementById('player2').innerText = name
}

function writeField(field) {
    let html = "<table>"
    field.forEach((row) => {
        html += "<tr>"

        row.forEach((col) => {
            html += "<td>" + col + "</td>"
        })

        html += "</tr>"
    })

    html += "</table>"

    document.getElementById('field').innerHTML = html
}

function newFrame(frame) {
    writePlayer1(frame.players["-1"])
    writePlayer2(frame.players["1"])
    writeField(frame.field)
}

sdk.subscribe_to_frame(newFrame)