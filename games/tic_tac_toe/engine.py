import time
from copy import deepcopy
import ge_sdk as sdk


def game():
    engine = sdk.GameEngineClient()
    stats = sdk.GameEngineStats(engine.teams, ["Количество ходов"])

    field = [
        [0] * 5,
        [0] * 5,
        [0] * 5,
        [0] * 5,
        [0] * 5
    ]

    engine.start()

    players = []

    for player, role in zip([engine.teams[0].players[0], engine.teams[1].players[0]], (-1, 1)):
        player.role = role
        players.append(player)

    step = 0
    while True:
        start = time.time()

        current_player = players[step % 2]
        x, y = sdk.timeout_run(0.4, current_player.script, "make_choice", (deepcopy(field), current_player.role))

        if x < 0 or x > 4 or y < 0 or y > 4:
            continue

        if field[x][y] != 0:
            continue

        field[x][y] = current_player.role

        step += 1

        stats.add_value(current_player, "Количество ходов", 1)

        frame = {
            "players": {
                "-1": players[0].name,
                "1": players[1].name
            },
            "field": field
        }

        engine.send_frame(frame)
        engine.send_stats(stats)

        if no_moves(field):
            break

        end = time.time()
        print(f"Step {step} took {round(end - start, 1)} seconds")
        time.sleep(1)

    engine.end()


def no_moves(field):
    return not any([0 in row for row in field])


if __name__ == "__main__":
    game()
