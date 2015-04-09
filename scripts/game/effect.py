from game import CEffect
from game import Damage
from game import game_object
from game import CEffect

@game_object
class Stun(CEffect):
    def onEffect(self):
        return True

@game_object
class EndlessPainEffect(CEffect):
    def onEffect(self):
        self.getVictim().hurt(self.getCaster().getDmg()*15//100)
        return True

@game_object
class AbyssalShadowsEffect(CEffect):
    def onEffect(self):
        dmg=Damage()
        if self.getTimeLeft() > 1:
            dmg.setNumericProperty('shadow',self.getCaster().getDmg()*45//100)
        else:
            dmg.setNumericProperty('shadow',self.getCaster().getDmg())
        self.getVictim().hurt(dmg)
        return False

@game_object
class ArmorOfEndlessWinterEffect(CEffect):
    def onEffect(self):
        self.getVictim().healProc ( 20 );
        return False #must implement ban to other skills

@game_object
class MutilationEffect(CEffect):
    def onEffect(self):
        self.getVictim().hurt ( self.getCaster().getStats().getNumericProperty('agility') //4 )
        return False;

@game_object
class LethalPoisonEffect(CEffect):
    def onEffect(self):
        self.getVictim().hurt ( self.getCaster().getDmg() * 4 // 6)
        return False;

@game_object
class BloodlashEffect(CEffect):
    def onEffect(self):
        self.getVictim().hurt ( self.getCaster().getDmg() * 0.75 )
        return False;

@game_object
class ChloroformEffect(CEffect):
    def onEffect(self):
        return self.getVictim().getHpRatio() > 25

@game_object
class BarrierEffect(CEffect):
    def onEffect(self):
        return False
