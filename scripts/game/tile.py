from game import CTile
from game import game_object

@game_object
class RoadTile(CTile):
    def onStep(self,creature):
        creature.heal(1)
