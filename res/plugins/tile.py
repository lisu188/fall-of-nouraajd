def load(self, context):
    from game import CTile
    from game import register

    @register(context)
    class RoadTile(CTile):
        def onStep(self, creature):
            creature.heal(1)
