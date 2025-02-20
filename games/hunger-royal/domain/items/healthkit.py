from domain.common import *
from domain.item import Item
from domain.player import Player


class HealthKit(Item):
    def __init__(self):
        super().__init__()

    def apply(self, object: Player):
        object.properties['max_lifes'] =+ 1
        object.properties['life'] = object.properties['max_lifes']
