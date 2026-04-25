from domain.general_player import GeneralPlayer


def tower_choice(x, y, state):
    me = state[x][y]['player']
    distance = me['properties']['fire_distance']
    width = len(state)
    height = len(state[0]) if width else 0

    for i in range(x - 1, x - distance - 1, -1):
        if i < 0:
            break
        if state[i][y]['player']:
            if state[i][y]['player']['properties'].get('team') != me['properties'].get('team'):
                return "fire_left"
            else:
                break
    for i in range(x + 1, x + distance + 1):
        if i >= width:
            break
        if state[i][y]['player']:
            if state[i][y]['player']['properties'].get('team') != me['properties'].get('team'):
                return "fire_right"
            else:
                break
    for i in range(y - 1, y - distance - 1, -1):
        if i < 0:
            break
        if state[x][i]['player']:
            if state[x][i]['player']['properties'].get('team') != me['properties'].get('team'):
                return "fire_up"
            else:
                break
    for i in range(y + 1, y + distance + 1):
        if i >= height:
            break
        if state[x][i]['player']:
            if state[x][i]['player']['properties'].get('team') != me['properties'].get('team'):
                return "fire_down"
            else:
                break


class Tower(GeneralPlayer):
    def __init__(self, team='Neutral'):
        super().__init__()

        self.decider = tower_choice

        self.properties = {
            'speed': 0,
            'power': 3,
            'life': 10,
            'fire_distance': 4,
            'name': 'tower',
            'team': team
        }
