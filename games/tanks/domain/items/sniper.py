from domain.common import *
from domain.item import Item
from domain.player import Player


class SniperBooster(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        booster = Booster('fire_distance', 50, 10)
        booster.apply(object)

        object.boosters.append(booster)
