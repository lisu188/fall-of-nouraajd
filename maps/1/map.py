class event1(game.CEvent):
    def onEnter(self):
        self.getMap().getGuiHandler().showMessage("dupa")


