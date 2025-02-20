from domain.common import *
from domain.item import Item
from domain.player import Player

class BlueKey(Item):
    def __init__(self):
        super().__init__()
        self.type = "BlueKey"
class YellowKey(Item):
    def __init__(self):
        super().__init__()
        self.type = "YellowKey"
class PinkKey(Item):
    def __init__(self):
        super().__init__()
        self.type = "PinkKey"