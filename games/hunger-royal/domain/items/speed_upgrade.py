from domain.common import *
from domain.item import Item
from domain.player import Player

class SpeedUpgrade(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        object.boosters.append(Booster("speed", 1, 10))