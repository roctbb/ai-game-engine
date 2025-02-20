import random
from math import sqrt
from domain.common import *
from domain.items import *

class Game:
    def __init__(self):
        self.size = (0, 0)
        self.players = {}
        self.items = {}
        self.objects = {}
        self.backgrounds = {}

    def get_state(self):
        state = [[{"player": None, "items": [], "object": None} for _ in range(self.height)] for _ in range(self.width)]

        for (x, y), player in self.players.items():
            state[x][y]['player'] = player.as_dict(Point(x, y))

        for (x, y), item in self.items.items():
            state[x][y]['items'] = item.as_dict(Point(x, y))

        for (x, y), object in self.objects.items():
            state[x][y]['object'] = object.as_dict(Point(x, y))

        return state
    def flood(MAP, point):
        for y in range(len(MAP)):
            for x in range(len(MAP[y])):
                for i in range(150):
                    if sqrt((x - point[0])**2 + (y - point[1])**2) > 150 - i:
                        MAP[y][x] = '&' 
    def get(self, point: Point):
        if not point:
            return None
        if (point.x, point.y) in self.players:
            return self.players.get((point.x, point.y))
        if (point.x, point.y) in self.objects:
            return self.objects.get((point.x, point.y))
        return None

    def move(self, point: Point, to_point: Point):
        if (point.x, point.y) in self.players:
            self.players[(to_point.x, to_point.y)] = self.players[(point.x, point.y)]
            del self.players[(point.x, point.y)]

    def delete(self, point: Point):
        if (point.x, point.y) in self.players:
            del self.players[(point.x, point.y)]
        if (point.x, point.y) in self.objects and not self.objects[(point.x, point.y)].is_transparent:
            del self.objects[(point.x, point.y)]

    def can_move(self, point: Point) -> bool:
        if point.x < 0 or point.x >= self.width:
            return False
        if point.y < 0 or point.y >= self.height:
            return False
        if self.get(point) == 2 and 1==1:
            pass
        return self.get(point) == None or self.get(point).is_transparent == True

    def can_attack(self, point: Point) -> bool:
        return self.get(point) != None and self.get(point).is_flat == False

    def as_dict(self, events=()):
        return {
            "players": [player.as_dict(Point(x, y)) for (x, y), player in self.players.items()],
            "items": [item.as_dict(Point(x, y)) for (x, y), item in self.items.items()],
            "objects": [object.as_dict(Point(x, y)) for (x, y), object in self.objects.items()],
            "backgrounds": [object.as_dict(Point(x, y)) for (x, y), object in self.backgrounds.items()],
            "events": [event.as_dict() for event in events],
            "width": self.width,
            "height": self.height
        }

    def make_step(self):
        state = self.get_state()

        attackers = []
        runners = []
        events = []

        for (x, y), player in self.players.items():
            decision = player.step(Point(x, y), state)

            if decision in Decision.moves():
                runners.append((player, Point(x, y), decision))

            if decision in Decision.attacks():
                attackers.append((player, Point(x, y), decision))

        for player, point, decision in runners:
            es = self.apply_move(player, point, decision)
            if es:
                events.extend(es)

        for player, point, decision in attackers:
            es = self.apply_attack(player, point, decision)
            if es:
                events.extend(es)

        return self.as_dict(events)

    def apply_attack(self, player, point, decision):
        if decision == Decision.FIRE_LEFT:
            player.rotate(Direction.LEFT)
        if decision == Decision.FIRE_RIGHT:
            player.rotate(Direction.RIGHT)
        if decision == Decision.FIRE_DOWN:
            player.rotate(Direction.DOWN)
        if decision == Decision.FIRE_UP:
            player.rotate(Direction.UP)

        power = player.properties.get('power')
        if not power:
            return []
        distance = player.properties.get('fire_distance')
        if not distance:
            return []

        x = point.x
        y = point.y

        attack_point = None
        if decision == Decision.FIRE_LEFT:
            for i in range(x - 1, max(-1, x - distance - 1), -1):
                attack_point = Point(i, y)
                if self.can_attack(Point(i, y)):
                    break

        elif decision == Decision.FIRE_RIGHT:
            for i in range(x + 1, min(x + distance + 1, self.width)):
                attack_point = Point(i, y)
                if self.can_attack(Point(i, y)):
                    break

        if decision == Decision.FIRE_UP:
            for i in range(y - 1, max(-1, y - distance - 1), -1):
                attack_point = Point(x, i)
                if self.can_attack(Point(x, i)):
                    break

        elif decision == Decision.FIRE_DOWN:
            for i in range(y + 1, min(y + distance + 1, self.height)):
                attack_point = Point(x, i)
                if self.can_attack(Point(x, i)):
                    break

        events = []

        team = player.properties.get('team', 'Neutral')

        if attack_point:
            if self.can_attack(attack_point):
                target = self.get(attack_point)
                target.attack(power)

                if not target.alive():
                    try:
                        if target.inventory.items():
                            self.items[(attack_point.x, attack_point.y)] = random.choice(
                                [item for item in target.inventory.items()])
                            target.inventory = None

                    except:
                        pass
                    events.append(Event("death", {"at": (attack_point.x, attack_point.y)}))
                    self.delete(Point(attack_point.x, attack_point.y))

            events.append(Event("shot", {"from": (x, y), "to": (attack_point.x, attack_point.y), 'team': team}))
        return events

    def apply_move(self, player, point, decision):
        if decision == Decision.GO_LEFT:
            player.rotate(Direction.LEFT)
        if decision == Decision.GO_RIGHT:
            player.rotate(Direction.RIGHT)
        if decision == Decision.GO_DOWN:
            player.rotate(Direction.DOWN)
        if decision == Decision.GO_UP:
            player.rotate(Direction.UP)

        x = point.x
        y = point.y

        speed = player.properties.get('speed')
        if not speed:
            return

        new_point = None

        if decision == Decision.GO_LEFT:
            for _ in range(speed):
                if self.can_move(Point(x - 1, y)):
                    if (Point(x - 1, y) == 2 and player.inventory.has("YellowKey")) or (Point(x - 1, y) == 6 and player.inventory.has("PinkKey")) or (Point(x - 1, y) == 9 and player.inventory.has("BlueKey")):
                        new_point = Point(x - 1, y)

        elif decision == Decision.GO_RIGHT:
            for _ in range(speed):
                if self.can_move(Point(x + 1, y)):
                    if (Point(x - 1, y) == 2 and player.inventory.has("YellowKey")) or (Point(x - 1, y) == 6 and player.inventory.has("PinkKey")) or (Point(x - 1, y) == 9 and player.inventory.has("BlueKey")):
                        new_point = Point(x + 1, y)

        if decision == Decision.GO_UP:
            for _ in range(speed):
                if self.can_move(Point(x, y - 1)):
                    if (Point(x - 1, y) == 2 and player.inventory.has("YellowKey")) or (Point(x - 1, y) == 6 and player.inventory.has("PinkKey")) or (Point(x - 1, y) == 9 and player.inventory.has("BlueKey")):
                        new_point = Point(x, y - 1)

        elif decision == Decision.GO_DOWN:
            for _ in range(speed):
                if self.can_move(Point(x, y + 1)):
                    if (Point(x - 1, y) == 2 and player.inventory.has("YellowKey")) or (Point(x - 1, y) == 6 and player.inventory.has("PinkKey")) or (Point(x - 1, y) == 9 and player.inventory.has("BlueKey")):
                        new_point = Point(x, y + 1)

        if new_point:

            self.move(Point(x, y), new_point)

            x = new_point.x
            y = new_point.y

            # забираем предметы в ячейке
            item = self.items.get((x, y))
            if item:
                player.inventory.add(item)
                del self.items[(x, y)]

        return []

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]
