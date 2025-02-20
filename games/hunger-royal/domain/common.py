from dataclasses import dataclass
from enum import Enum


@dataclass
class Point:
    x: int
    y: int


class Direction(str, Enum):
    LEFT = "left"
    UP = "up"
    RIGHT = "right"
    DOWN = "down"
    NO = "no"

    @classmethod
    def directions(cls):
        return [cls.LEFT, cls.RIGHT, cls.DOWN, cls.UP]


class Decision(str, Enum):
    FIRE_UP = "fire_up"
    FIRE_LEFT = "fire_left"
    FIRE_RIGHT = "fire_right"
    FIRE_DOWN = "fire_down"
    GO_UP = "go_up"
    GO_LEFT = "go_left"
    GO_RIGHT = "go_right"
    GO_DOWN = "go_down"
    USE = "use"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_

    @classmethod
    def attacks(cls):
        return (cls.FIRE_UP, cls.FIRE_DOWN, cls.FIRE_LEFT, cls.FIRE_RIGHT)

    @classmethod
    def moves(cls):
        return (cls.GO_UP, cls.GO_DOWN, cls.GO_LEFT, cls.GO_RIGHT)


@dataclass
class Position:
    point: Point
    direction: Direction


class Booster:
    def __init__(self, property, value, ticks):
        self.property = property
        self.ticks_left = ticks
        self.value = value

    def tick(self):
        self.ticks_left -= 1

    def over(self):
        return self.ticks_left <= 0

    def apply(self, object):
        if self.property in object.properties:
            object.properties[self.property] += self.value

    def deapply(self, object):
        if self.property in object.properties:
            object.properties[self.property] -= self.value


class Event:
    def __init__(self, type, params):
        self.type = type
        self.params = params

    def as_dict(self):
        return {
            "type": self.type,
            "params": self.params
        }


class Object:
    def __init__(self):
        self.direction = Direction.NO
        self.properties = {}
        self.is_flat = False
        self.is_transparent = False

    def attack(self, power: int):
        if 'life' in self.properties:
            self.properties['life'] -= power

    def alive(self) -> bool:
        return self.properties.get('life', 0) > 0

    def as_dict(self, point: Point = None):
        description = {
            "direction": self.direction,
            "properties": self.properties,
            "type": self.type,
        }

        if point:
            description["x"] = point.x
            description["y"] = point.y

        return description

    @property
    def type(self):
        return self.__class__.__name__
