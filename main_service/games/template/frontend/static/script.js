const sdk = new GeSdk()
const path = '/games/GAME_TITLE/static/'

// Пример пути к картинке:
// path + 'images/image.png'

let canvas;

function init() {
    canvas = document.getElementById("field");
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

function newFrame(frame) {
    // Отрисовка кадра на экране
    console.log(frame)
}

init()
sdk.subscribe_to_frame(newFrame)
