def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import register
    from game import trigger

    @register(context)
    class SpawnPoint(CEvent):
        def onCreate(self, event):
            self.setBoolProperty('enabled', False)

        def onTurn(self, event):
            if self.getBoolProperty('enabled'):
                self.getMap().addObjectByName('Pritz', self.getCoords())

    @trigger(context, "onTurn", "triggerAnchor")
    class TurnTrigger(CTrigger):
        def trigger(self, object, event):
            if (object.getMap().getTurn() + 1 % 25) == 0:
                print(object.getMap().getTurn())
                event.cont = True

                def enableSpawn(spawnObject):
                    spawnObject.getMap().replaceTile('GrassTile', spawnObject.getCoords())
                    spawnObject.setBoolProperty('enabled', True)
                    event.cont = False

                object.getMap().forObjects(enableSpawn, lambda ob: event.cont and ob.getStringProperty(
                    'type') == 'SpawnPoint' and not ob.getBoolProperty('enabled'))
