from domain.common import Object, Position, Decision, Point, Direction
from domain.inventory import Inventory
from typing import Tuple, Callable, Optional
import traceback


class GeneralPlayer(Object):
    def __init__(self):
        super().__init__()

        self.direction = Direction.LEFT
        self.inventory = Inventory()
        self.decider = lambda x, y, s: None

        self.properties = {
            'speed': 1,
            'power': 1,
            'life': 10,
            'fire_distance': 10
        }

        self.history = []
        self.errors = []
        self.boosters = []

    def as_dict(self, point):
        base = super().as_dict(point)
        base['errors'] = [str(e) for e in self.errors]
        base['history'] = self.history
        base['inventory'] = [item.as_dict() for item in self.inventory.items()]
        return base

    def step(self, point: Point, map_state) -> Optional[Decision]:
        try:
            choice = self.decider(point.x, point.y, map_state)
        except Exception as e:
            self.errors.append(e)
            self.history.append("crash")
            print(traceback.format_exc(), e)
            return

        if not choice:
            self.errors.append(Exception("No choice"))
            self.history.append("no_choice")
            return

        parts = choice.split(" ")

        if not Decision.has_value(parts[0]):
            self.errors.append(Exception("Invalid choice: " + choice))
            self.history.append("invalid_choice")
            return
        else:
            self.history.append(choice)

        if parts[0] == Decision.USE:
            if len(parts) != 2:
                self.errors.append(Exception("Invalid choice: " + choice))
                self.history.append("invalid_choice")
                return
            item = self.inventory.pop(parts[1])
            if not item:
                self.errors.append(Exception("No item in inventory: " + choice))
                self.history.append("invalid_choice")
                return

            item.apply(self)
            return None
        else:
            return parts[0]

    def rotate(self, direction: Direction):
        self.direction = direction
