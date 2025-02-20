from domain.common import *
from domain.item import Item
from domain.player import Player


class NuclearBomb(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        object.boosters.append(Booster("can_make_big_boom", True, 150))
