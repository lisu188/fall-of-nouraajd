def load(self, context):
    from game import CEvent
    from game import CTrigger
    from game import register
    from game import trigger
    from game import randint
    from game import logger

    @register(context)
    class SpawnPoint(CEvent):
        def onCreate(self, event):
            self.setStringProperty("animation", "images/misc/closed_door")
            self.setBoolProperty('enabled', False)
            self.setBoolProperty('destroyed', False)

        def onTurn(self, event):
            if self.getBoolProperty('enabled') and not self.getBoolProperty('destroyed') and randint(1, 10) == 10:
                logger("Spawning new creature")
                if randint(1, 10) == 10:
                    logger("Spawning mage")
                    self.getMap().addObjectByName('siegePritzMage', self.getCoords())
                else:
                    logger("Spawning grunt")
                    self.getMap().addObjectByName('siegePritz', self.getCoords())

        def onEnter(self, event):
            if event.getCause().isPlayer():
                if self.getMap().getPlayer().hasItem(lambda it: it.hasTag('wand')):
                    if self.getMap().getGame().getGuiHandler().showQuestion(
                            "Do You want to seal the gate?"):
                        self.getMap().getPlayer().removeQuestItem(lambda it: it.hasTag('wand'))
                        self.setBoolProperty('destroyed', True)
                        self.setStringProperty("animation", "images/misc/closed_door")
                        self.setBoolProperty("canStep", False)
                else:
                    self.getMap().getGame().getGuiHandler().showInfo("You need a wand to seal the gate!")

    @trigger(context, "onTurn", "triggerAnchor")
    class TurnTrigger(CTrigger):
        def trigger(self, object, event):
            if randint(1, 25) == 25:
                event.cont = True

                def enableSpawn(spawnObject):
                    logger("Spawning gate")
                    spawnObject.getMap().replaceTile('SwampTile', spawnObject.getCoords())
                    spawnObject.setBoolProperty('enabled', True)
                    # TODO: autoexport set get property
                    spawnObject.setStringProperty("animation", "images/misc/open_door")
                    event.cont = False

                object.getMap().forObjects(enableSpawn, lambda ob: event.cont and ob.getStringProperty(
                    'type') == 'SpawnPoint' and not ob.getBoolProperty('enabled'))
