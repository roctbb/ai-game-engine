import json
import time
import redis
from domain.game import Game
from domain.maps.default import DefaultMap
from domain.maps.big import BigMap
from domain.maps.tanks import TankMap
import time
from copy import deepcopy
import ge_sdk as sdk


def game():
    engine = sdk.GameEngineClient()
    stats = sdk.GameEngineStats(engine.teams, ["Количество ходов"])

    players = []
    for team in engine.teams:
        players.append(team.players[0])

    game = Game()
    TankMap.init(game, players)

    for step in range(120):
        frame = game.make_step()
        engine.send_frame(frame)

    engine.end()

if __name__ == '__main__':
    game()
