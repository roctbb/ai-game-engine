from domain.common import *


class Door(Object):
    def __init__(self):
        super().__init__()

        self.is_flat = False
        self.is_transparent = True
