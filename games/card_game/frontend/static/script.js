const sdk = new GeSdk()
const path = '/games/card_game/static/'

let canvas;

var images = {}

// функция для скачивания всех изображений
function loadImages() {
    return new Promise((resolve) => {
        let loaded = 0;

        const image_loaded = () => {
            loaded++;
            if (loaded === Object.keys(images).length) resolve();
        }

        // Generate the array of image names
        const imageNames = [];
        for (let _ = 0; _ < 13; _++) {
            for (let suit = 0; suit < 4; suit++) {
                imageNames.push(`${_ + 2}-${suit + 1}`);
            }
        }
        imageNames.push("BACK")

        // Load each image
        imageNames.forEach((imageName) => {
            images[imageName] = new Image();
            images[imageName].onload = image_loaded;
            images[imageName].src = path + "images/" + imageName + ".png";
        })
    })
}

function clearScreen(ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function drawPlayersAndScores(ctx, players, scores, hands, discards, wins) {
    ctx.font = "24px serif";

    const topName = `Игрок 1: ${players['top']}`
    const bottomName = `Игрок 2: ${players['bottom']}`

    const topScore = `Счет: ${scores['top']}`
    const bottomScore = `Счет: ${scores['bottom']}`

    const topHands = `Руки: ${hands['top']}`
    const bottomHands = `Руки: ${hands['bottom']}`

    const topDiscards = `Сбросов: ${discards['top']}`
    const bottomDiscards = `Сбросов: ${discards['bottom']}`

    const topWins = `Побед: ${wins['top']}`
    const bottomWins = `Побед: ${wins['bottom']}`

    const BDW = ctx.measureText(bottomDiscards).width;
    const TDW = ctx.measureText(topDiscards).width;
    const BHW = ctx.measureText(bottomHands).width;
    const THW = ctx.measureText(topHands).width;

    ctx.fillText(topName, 70, 30);
    ctx.fillText(topScore, 70, 70);
    ctx.fillText(topWins, 70, 110);

    ctx.fillText(bottomName, 70, canvas.height - 24 - 30);
    ctx.fillText(bottomScore, 70, canvas.height - 24 - 70);
    ctx.fillText(bottomWins, 70, canvas.height - 24 - 110);

    ctx.fillText(topHands, canvas.width-THW-70, 30);
    ctx.fillText(topDiscards, canvas.width-TDW-70, 70);

    ctx.fillText(bottomHands, canvas.width-BHW-70, canvas.height-54);
    ctx.fillText(bottomDiscards, canvas.width-BDW-70, canvas.height-94);
}

function drawChoices(ctx, cards, cardsChosen) {
    for (var i = 0; i < cards['top'].length; i++) {
        ctx.drawImage(images[cards['top'][i]], canvas.width/2+(i-4)*80, 70, 70, 100);
        // toDraw.push(images[cards[i]])
    }
    for (var i = 0; i < cards['bottom'].length; i++) {
        ctx.drawImage(images[cards['bottom'][i]], canvas.width/2+(i-4)*80, canvas.height-170, 70, 100);
        // toDraw.push(images[cards[i]])
    }
}

function drawWinner(ctx, winner, players) {
    if (winner) {
        winner = players[winner]

        ctx.font = "48px serif";
        ctx.fillStyle = 'green';

        const text = `Победитель: ${winner}`
        const size = ctx.measureText(text);

        ctx.fillText(text, canvas.width/2-size.width/2, canvas.height/2-24);
    }
}

function init() {
    canvas = document.getElementById("field");
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    // Load images and then start the game loop or other initialization
    loadImages().then(() => {
        console.log("All images loaded");
        // You can start your game loop or other initialization here
    });

}

function newFrame(frame) {
    let ctx = canvas.getContext("2d");

    clearScreen(ctx)
    console.log(frame)
    drawPlayersAndScores(ctx, frame['players'], frame['points'], frame['handsLeft'], frame['discardsLeft'], frame['wins'])
    drawChoices(ctx, frame['cardsInHand'], frame['cardsChosen'])
    drawWinner(ctx, frame['winner'], frame['players'])
}

init()
sdk.subscribe_to_frame(newFrame)
