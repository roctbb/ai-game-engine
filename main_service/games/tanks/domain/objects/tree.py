import random

from domain.common import *


class Tree(Object):
    def __init__(self):
        super().__init__()
        self.direction = random.choice(Direction.directions())

        self.properties = {
            "life": 3,
        }
