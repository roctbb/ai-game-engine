import time
from copy import deepcopy

import ge_sdk as sdk


def buildFrame(players, field, winner_value=None):
    frame = {
        "players": {
            "-1": players[0].name,
            "1": players[1].name
        },
        "field": field,
    }

    if winner_value:
        frame['winner'] = winner_value

    return frame


def createEmptyField():
    return [
        [0] * 5,
        [0] * 5,
        [0] * 5,
        [0] * 5,
        [0] * 5
    ]


def checkDirection(field, start_x, start_y, d_x, d_y, n, value):
    number = 0

    for i in range(n):
        if field[start_x + d_x * i][start_y + d_y * i] == value:
            number += 1
        else:
            number = 0

        if number == 4:
            return True

    return False


def checkLine(field, line, value):
    return checkDirection(field, 0, line, 1, 0, 5, value)


def checkColumn(field, column, value):
    return checkDirection(field, column, 0, 0, 1, 5, value)


def checkDiags(field, value):
    result = True
    result = result and checkDirection(field, 0, 0, 1, 1, 5, value)
    result = result and checkDirection(field, 4, 0, -1, 1, 5, value)
    result = result and checkDirection(field, 1, 0, 1, 1, 4, value)
    result = result and checkDirection(field, 0, 1, 1, 1, 4, value)
    result = result and checkDirection(field, 3, 0, -1, 1, 4, value)
    result = result and checkDirection(field, 4, 1, -1, 1, 4, value)

    return result


def checkForWin(field):
    for value in [1, -1]:
        for i in range(5):
            if checkLine(field, i, value) or checkColumn(field, i, value):
                return value

        if checkDiags(field, value):
            return value

    return 0


def no_moves(field):
    return not any([0 in row for row in field])


def game():
    engine = sdk.GameEngineClient()
    stats = sdk.GameEngineStats(engine.teams, ["Количество ходов"])

    field = createEmptyField()

    engine.start()

    players = []

    for player, role in zip([engine.teams[0].players[0], engine.teams[1].players[0]], (-1, 1)):
        player.role = role  # type: ignore
        players.append(player)

    step = 0
    while True:
        start = time.time()

        current_player = players[step % 2]
        try:
            x, y = sdk.timeout_run(
                0.4,
                current_player.script,
                "make_choice",
                (deepcopy(field), current_player.role),
                bypass_errors=False
            )
        except TimeoutError:
            break

        if x < 0 or x > 4 or y < 0 or y > 4:
            continue

        if field[x][y] != 0:
            continue

        field[x][y] = current_player.role

        step += 1

        stats.add_value(current_player, "Количество ходов", 1)

        frame = buildFrame(players, field)
        engine.send_frame(frame)
        engine.send_stats(stats)

        if no_moves(field) or checkForWin(field):
            break

        end = time.time()
        print(f"Step {step} took {round(end - start, 1)} seconds")
        time.sleep(1)

    if not no_moves(field):
        if current_player == engine.teams[0].players[0]:
            engine.set_winner(engine.teams[0])
        else:
            engine.set_winner(engine.teams[1])

    frame = buildFrame(players, field, checkForWin(field))
    engine.send_frame(frame)

    engine.end()


if __name__ == "__main__":
    game()
