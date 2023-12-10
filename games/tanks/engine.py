import json
import time
from domain.game import Game
from domain.maps.default import DefaultMap
from domain.maps.big import BigMap
import ge_sdk as sdk
from domain.repositories.players import PlayersRepository

engine = sdk.GameEngineClient()
stats = sdk.GameEngineStats(engine.teams, ["Количество ходов"])
engine.start()


def buildTeam(team, type):
    return [
        {
            "id": player.id,
            "team": type,
            "name": player.name,
            "script": player.script
        } for player in team.players
    ]


def buildDescriptions(teams):
    descriptions = buildTeam(teams[0], 'Radient')
    descriptions.extend(buildTeam(teams[1], 'Dare'))

    return descriptions


while True:
    game = Game()
    BigMap.init(game, buildDescriptions(engine.teams))

    for step in range(120):
        frame = game.make_step()
        engine.send_frame(frame)
        time.sleep(0.5)

    engine.end()
