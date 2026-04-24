from domain.common import Object

class Item(Object):
    def __init__(self):
        super().__init__()

    def apply(self, player):
        # Base items are allowed to be no-op; concrete boosters/consumables override.
        return None
