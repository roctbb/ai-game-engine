import sys
import imp

from domain.general_player import GeneralPlayer


class Player(GeneralPlayer):
    def __init__(self, description, properties={}):
        super().__init__()

        self.id = description.get('id')
        self.properties['name'] = description.get('name')
        self.decider = description.get('script').make_choice

        for key in properties:
            self.properties[key] = properties[key]

    def step(self, point, map_state):
        for booster in self.boosters[:]:
            booster.tick()
            if booster.over():
                self.boosters.remove(booster)

        return super(Player, self).step(point, map_state)
