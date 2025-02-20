import sys
from domain.general_player import GeneralPlayer
import ge_sdk as sdk


class Player(GeneralPlayer):
    def __init__(self, player, properties={}):
        super().__init__()

        self.player = player

        for key in properties:
            self.properties[key] = properties[key]

    def _update_decider(self):

        self.decider = lambda x, y, map_state: sdk.timeout_run(0.4, self.player.script, "make_choice", (x, y, map_state))
    def step(self, point, map_state):
        for booster in self.boosters[:]:
            booster.tick()
            if booster.over():
                self.boosters.remove(booster)
        self._update_decider()
        return super(Player, self).step(point, map_state)
