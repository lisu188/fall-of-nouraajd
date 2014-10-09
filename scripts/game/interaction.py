from game import Damage
from game import Stats
from game import CInteraction
from game import randint

class Attack(CInteraction):
    def performAction(self,first,second):
        dmg = first.getDmg()
        if dmg:
            second.hurt( dmg )
            weapon = first.getWeapon()
            if weapon:
                inter= weapon.getInteraction()
                if inter:
                    inter.onAction ( first, second );

class ElemStaff(CInteraction):
    def performAction(self,first,second):
        damage=Damage()
        damage.setNumericProperty('fire',1)
        damage.setNumericProperty('frost',1)
        damage.setNumericProperty('thunder',1)
        second.hurt ( damage )

class DoubleAttack(CInteraction):
    def performAction ( self,first,second ):
        Attack().onAction(first, second)
        Attack().onAction(first, second)

class SneakAttack(Attack):
    def performAction( self,first,second ):
        super(SneakAttack,self).performAction(first, second)
        if randint(1,100) > ( 100 - second.getHpRatio()) and second.isAlive():
            super(SneakAttack,self).performAction(first, second)

class Strike(CInteraction):
    def performAction ( self,first, second ):
        if first.getWeapon():
            dmg = first.getDmg();
            if dmg:
                second.hurt ( dmg + first.getStats().getNumericProperty('damage'))

class ChaosBlast(CInteraction):
    def performAction (self,first, second ):
        damage=Damage()
        damage.setNumericProperty('fire',first.getMana() // 2)
        damage.setNumericProperty('thunder',first.getMana() // 2)
        second.hurt ( damage );

class Devour(CInteraction):
    def performAction ( self,first, second ):
        crit = first.getStats().getNumericProperty('crit')
        first.getStats().setNumericProperty('crit', 0 )
        dmg = first.getDmg()
        if  dmg :
            second.hurt ( dmg )
            first.healProc ( ( dmg * 0.75 ) // first.getHpMax() * 100 )
        first.getStats().setNumericProperty('crit', crit )

class FrostBolt(CInteraction):
    def performAction (self, first, second ):
        Attack().onAction( first, second )
        damage=Damage()
        damage.setNumericProperty('frost', first.getStats().getNumericProperty('intelligence') * 75.0 // 100.0)
        second.hurt ( damage )

class MagicMissile(CInteraction):
    def performAction (self, first, second ):
        dmg = 0;
        for i in range(first.getLevel() // 2 + 1):
            dmg += randint(1,4) % 4 + 1;
        second.hurt ( dmg );

class ShadowBolt (CInteraction):
    def performAction( self,first, second ):
        damage=Damage();
        damage.setNumericProperty('shadow',first.getDmg() * 2.25 )
        second.hurt ( damage )

    def configureEffect(self,effect):
        if randint(1,2) == 0:
            damage.setNumericProperty('shadow',getCaster().getWeapon().getStats().getNumericProperty('damage'))
            getVictim().hurt ( damage )
            return True
        return False

class Mutilation (CInteraction):
    def performAction(self, first, second ):
        second.hurt ( first.getDmg() * 1.5 )

class LethalPoison(CInteraction):
    def performAction(self,first, second ):
        pass

class Bloodlash ( CInteraction):
    def performAction(self,first,second):
        second.hurt ( first.getDmg() * 1.5 )

class Backstab(CInteraction):
    def performAction (self, first,second ):
        second.hurt ( first.getDmg() * 1.75 )

    def configureEffect(self,effect):
        if randint(1,5) == 0:
            return True
        else:
            return False

class DeathStrike (CInteraction):
    def performAction(self, first, second ):
        second.hurt ( first.getDmg() * 2 )
        if  second.getHpRatio() < 20 :
            second.hurt ( first.getDmg() * 1.5 );

class BloodThirst(CInteraction):
    def performAction ( first, second ):
        second.hurt ( first.getDmg() * 0.2 )
        first.healProc ( 20 )

class AbyssalShadows(CInteraction):
    pass

class Barrier(CInteraction):
    pass

class Chloroform(CInteraction):
    pass

class EndlessPain(CInteraction):
    pass

class LethalPoison(CInteraction):
    pass

class Mutilation(CInteraction):
    pass

class Stunner(CInteraction):
    pass

class ArmorOfEndlessWinter(CInteraction):
    def configureEffect(self,effect):
        stats =Stats();
        stats.setNumericProperty('armor', (getCaster().getStats().getNumericProperty('armor') * 0.75 ));
        setBonus ( stats );

class Barrier ( CInteraction):
    def configureEffect(self,effect):
        firstgetCaster()
        stats =Stats();
        stats.setNumericProperty('armor', ( first.getStats().getNumericProperty('armor') * 0.5 ));
        stats.setNumericProperty('block', ( first.getStats().getNumericProperty('block') * 0.25 ));
        stats.setNumericProperty('damage', ( first.getStats().getNumericProperty('damage') * -0.5 ));
        setBonus ( stats );
