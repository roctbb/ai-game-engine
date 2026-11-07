# Первый маршрут — маленький прямоугольник. Улучшите выбор маршрута.
route = ["right"] * 4 + ["down"] * 4 + ["left"] * 4 + ["up"] * 4
step = 0


def make_move(state):
    global step
    action = route[step % len(route)]
    step += 1
    return action
