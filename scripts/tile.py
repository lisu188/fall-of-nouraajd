from game import CTile
from game import register

def load(context):
    @register(context)
    class RoadTile(CTile):
        def onStep(self,creature):
            creature.heal(1)
