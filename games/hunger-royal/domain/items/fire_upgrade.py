from domain.common import *
from domain.item import Item
from domain.player import Player

class PiwPaw(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        object.boosters.append(Booster("damage", True, 150))
class WallFight(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        object.boosters.append(Booster("shoot_wall", True, 150))