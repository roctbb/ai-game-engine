import json
import time
import redis
from domain.game import Game
from basicmap import InsaneMap
import time
from copy import deepcopy
import ge_sdk as sdk
from basicmap import MAP
def game():
    engine = sdk.GameEngineClient()
    stats = sdk.GameEngineStats(engine.teams, ["Количество ходов"])

    players = []
    for team in engine.teams:
        players.append(team.players[0])

    game = Game()
    InsaneMap.init(game, players)

    for step in range(100):
        frame = game.make_step()
        engine.send_frame(frame)
        if step % 3 == 0:
                game.flood(MAP, ())
                pass
    engine.end()

if __name__ == '__main__':
    game()
