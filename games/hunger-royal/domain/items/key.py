from domain.common import *
from domain.item import Item
from domain.player import Player

class BlueKey(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        object.boosters.append(Booster("OpenTheDoor_blue", True, 150))
class YellowKey(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        object.boosters.append(Booster("OpenTheDoor_yellow", True, 150))
class PinkKey(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        object.boosters.append(Booster("OpenTheDoor_pink", True, 150))