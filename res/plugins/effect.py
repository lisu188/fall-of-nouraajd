def load(self,context):
    from game import Damage
    from game import register
    from game import CEffect

    @register(context)
    class Stun(CEffect):
        def onEffect(self):
            pass

    @register(context)
    class EndlessPainEffect(CEffect):
        def onEffect(self):
            self.getVictim().hurt(self.getCaster().getDmg()*15//100)

    @register(context)
    class AbyssalShadowsEffect(CEffect):
        def onEffect(self):
            dmg=Damage()
            if self.getTimeLeft() > 1:
                dmg.setNumericProperty('shadow',self.getCaster().getDmg()*45//100)
            else:
                dmg.setNumericProperty('shadow',self.getCaster().getDmg())
            self.getVictim().hurt(dmg)


    @register(context)
    class ArmorOfEndlessWinterEffect(CEffect):
        def onEffect(self):
            self.getVictim().healProc(20)
            # must implement ban to other skills

    @register(context)
    class MutilationEffect(CEffect):
        def onEffect(self):
            self.getVictim().hurt ( self.getCaster().getStats().getNumericProperty('agility') //4 )


    @register(context)
    class LethalPoisonEffect(CEffect):
        def onEffect(self):
            self.getVictim().hurt ( self.getCaster().getDmg() * 4 // 6)

    @register(context)
    class BloodlashEffect(CEffect):
        def onEffect(self):
            self.getVictim().hurt ( self.getCaster().getDmg() * 0.75 )

    @register(context)
    class ChloroformEffect(CEffect):
        def onEffect(self):
            if self.getVictim().getHpRatio() > 25:
                self.removeTag('stun')
            else:
                self.addTag('stun')

    @register(context)
    class BarrierEffect(CEffect):
        def onEffect(self):
            pass
