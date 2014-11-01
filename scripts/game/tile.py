from game import CTile

class RoadTile(CTile):
    def onStep(self,creature):
        creature.heal(1)
