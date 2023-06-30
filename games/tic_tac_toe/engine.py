import time
from copy import deepcopy
import sdk


def no_moves(field):
    return not any([0 in row for row in field])


engine = sdk.GameEngineClient()

field = [
    [0] * 5,
    [0] * 5,
    [0] * 5,
    [0] * 5,
    [0] * 5
]

engine.start()

players = []

for player, role in zip([engine.teams[0]["players"][0], engine.teams[1]["players"][0]], (-1, 1)):
    players.append({
        "name": player["name"],
        "solver": engine.load_script("make_choice", player["script"]).make_choice,
        "role": role
    })

step = 0
while True:
    current_player = players[step % 2]
    x, y = current_player["solver"](deepcopy(field), current_player["role"])

    if x < 0 or x > 4 or y < 0 or y > 4:
        continue

    if field[x][y] != 0:
        continue

    field[x][y] = current_player["role"]

    if no_moves(field):
        break

    step += 1

    frame = {
        "players": {
            "-1": players[0]["name"],
            "1": players[1]["name"]
        },
        "field": field
    }

    engine.send_frame(frame)
    time.sleep(1)

engine.end()
