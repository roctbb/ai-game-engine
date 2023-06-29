import time
import sdk
import random

engine = sdk.GameEngineClient()

choices = ["tic", "tac", "toe"]

engine.start()
for i in range(100):
    frame = []

    for team in engine.teams:
        player = team["players"][0]

        frame.append({
            "player": player["name"],
            "choice": random.choice(choices)
        })

    engine.send_frame(frame)
    time.sleep(1)

engine.end()
