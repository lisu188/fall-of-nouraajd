def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import register
    from game import trigger
    from game import randint

    @register(context)
    class SpawnPoint(CEvent):
        def onCreate(self, event):
            self.setBoolProperty('enabled', False)

        def onTurn(self, event):
            if self.getBoolProperty('enabled') and randint(1, 10) == 10:
                self.getMap().addObjectByName('siegePritz', self.getCoords())

    @trigger(context, "onTurn", "triggerAnchor")
    class TurnTrigger(CTrigger):
        def trigger(self, object, event):
            if randint(1, 25) == 25:
                print(object.getMap().getTurn())
                event.cont = True

                def enableSpawn(spawnObject):
                    spawnObject.getMap().replaceTile('GrassTile', spawnObject.getCoords())
                    spawnObject.setBoolProperty('enabled', True)
                    event.cont = False

                object.getMap().forObjects(enableSpawn, lambda ob: event.cont and ob.getStringProperty(
                    'type') == 'SpawnPoint' and not ob.getBoolProperty('enabled'))
