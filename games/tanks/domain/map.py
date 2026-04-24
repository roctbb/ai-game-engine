from domain.game import Game


class Map:
    @classmethod
    def init(self, game: Game):
        raise NotImplementedError("Map.init must be implemented by a concrete map class")
