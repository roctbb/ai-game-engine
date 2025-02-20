from typing import Tuple, Optional
from domain.item import Item


class Inventory:
    def __init__(self, startpack: Tuple[Item] = ()):
        self._items = []

        for item in startpack:
            self.add(item)

    def add(self, item: Item) -> None:
        self._items.append(item)

    def items(self) -> Tuple[Item]:
        return tuple(self._items)

    def pop(self, title: str) -> Optional[Item]:
        try:
            item = next(item for item in self._items if item.type == title)
        except Exception as e:
            return None

        self._items.remove(item)
        return item
    
    def has(self, title: str) -> Optional[Item]:
        try:
            item = next(item for item in self._items if item.type == title)
        except Exception as e:
            return False
        return True
