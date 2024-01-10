const sdk = new GeSdk()
const path = '/games/tic_tac_toe/static/'

let canvasW = 640;
let canvasH = 640;

const cross_img = new Image(); // Create new img element
const zero_img = new Image(); // Create new img element

function load_images() {

    return new Promise((resolve, reject) => {
        let loaded = 0;
        cross_img.src = path + "/images/cross.png";
        zero_img.src = path + "/images/zero.png";

        const image_loaded = () => {
            loaded++;

            if (loaded === 2) {
                resolve();
            }
        }

        cross_img.onload = image_loaded
        zero_img.onload = image_loaded
    })

}


function init() {
    canvas = document.getElementById("field");
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    canvasW = canvas.width;
    canvasH = canvas.height;
}

function drawPlayers(ctx, players) {
    ctx.font = "24px serif";

    const player1_text = `Игрок 1: ${players[-1]}`
    const player2_text = `Игрок 2: ${players[1]}`

    const size1 = ctx.measureText(player1_text);
    const size2 = ctx.measureText(player2_text);

    console.log(size1, size2)

    ctx.fillText(player1_text, 70, 30);
    ctx.fillText(player2_text, 70, 70);

    ctx.drawImage(cross_img, 30, 5, 35, 35)
    ctx.drawImage(zero_img, 30, 45, 35, 35)
}

function drawWinner(ctx, winner) {
    if (winner) {
        let winnerText = ""
        let winnerImage = undefined

        if (winner === "-1") {
            winnerText = `Победил игрок 1!`
            winnerImage = cross_img
        } else {
            winnerText = `Победил игрок 2!`
            winnerImage = zero_img
        }

        ctx.font = "bold 24px serif";

        const size = ctx.measureText(winnerText);

        const marginLeft = Math.round((canvasW - size.width) / 2)

        ctx.fillText(winnerText, marginLeft, 30);
        ctx.drawImage(winnerImage, marginLeft + size.width + 10, 3, 40, 40)

    }

}

function drawTable(ctx, field) {
    const cellSize = Math.round(canvasH / 7)
    console.log(cellSize, canvasW, canvasH, window.innerHeight)

    const xMargin = Math.round((canvasW - cellSize * 5) / 2)

    for (let i = 0; i < 5; i++) {
        for (let j = 0; j < 5; j++) {
            const x = xMargin + cellSize * i
            const y = cellSize + cellSize * j

            let signSize = 100;
            let signMargin = 0;

            if (signSize > cellSize) {
                signSize = cellSize
            }

            if (signSize < cellSize) {
                signMargin = Math.round((cellSize - signSize) / 2)
            }

            if (field[i][j] === -1) {
                ctx.drawImage(cross_img, x + signMargin, y + signMargin, signSize, signSize)
            }
            if (field[i][j] === 1) {
                ctx.drawImage(zero_img, x + signMargin, y + signMargin, signSize, signSize)
            }

            ctx.strokeRect(x, y, cellSize, cellSize)
        }
    }
}

function newFrame(frame) {
    console.log(frame)
    const ctx = document.getElementById("field").getContext("2d");
    ctx.clearRect(0, 0, canvasW, canvasH);

    drawPlayers(ctx, frame["players"])
    drawWinner(ctx, frame["winner"])
    drawTable(ctx, frame["field"])

    console.log(frame)
}

init()
load_images().then(() => {
    sdk.subscribe_to_frame(newFrame)
})
