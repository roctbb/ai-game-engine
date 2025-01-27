from domain.common import *


class Wall(Object):
    def __init__(self):
        super().__init__()

        self.properties = {
            "life": 10,
        }
