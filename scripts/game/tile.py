from game import CTile

class RoadTile(CTile):
    def onStep(self,event):
        event.getCause().heal(1)
