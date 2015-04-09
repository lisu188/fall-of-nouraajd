from game import Damage
from game import Stats
from game import CInteraction
from game import randint
from game import game_object

@game_object
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

@game_object
class ElemStaff(CInteraction):
    def performAction(self,first,second):
        damage=Damage()
        damage.setNumericProperty('fire',1)
        damage.setNumericProperty('frost',1)
        damage.setNumericProperty('thunder',1)
        second.hurt ( damage )

@game_object
class DoubleAttack(CInteraction):
    def performAction ( self,first,second ):
        Attack().onAction(first, second)
        Attack().onAction(first, second)

@game_object
class SneakAttack(Attack):
    def performAction( self,first,second ):
        super(SneakAttack,self).performAction(first, second)
        if randint(1,100) > ( 100 - second.getHpRatio()) and second.isAlive():
            super(SneakAttack,self).performAction(first, second)

@game_object
class Strike(CInteraction):
    def performAction ( self,first, second ):
        if first.getWeapon():
            dmg = first.getDmg();
            if dmg:
                second.hurt ( dmg + first.getStats().getNumericProperty('damage'))

@game_object
class ChaosBlast(CInteraction):
    def performAction (self,first, second ):
        damage=Damage()
        damage.setNumericProperty('fire',first.getMana() // 2)
        damage.setNumericProperty('thunder',first.getMana() // 2)
        second.hurt ( damage );

@game_object
class Devour(CInteraction):
    def performAction ( self,first, second ):
        crit = first.getStats().getNumericProperty('crit')
        first.getStats().setNumericProperty('crit', 0 )
        dmg = first.getDmg()
        if  dmg :
            second.hurt ( dmg )
            first.healProc ( ( dmg * 0.75 ) // first.getHpMax() * 100 )
        first.getStats().setNumericProperty('crit', crit )

@game_object
class FrostBolt(CInteraction):
    def performAction (self, first, second ):
        Attack().onAction( first, second )
        damage=Damage()
        damage.setNumericProperty('frost', first.getStats().getNumericProperty('intelligence') * 75.0 // 100.0)
        second.hurt ( damage )

@game_object
class MagicMissile(CInteraction):
    def performAction (self, first, second ):
        dmg = 0;
        for i in range(first.getLevel() // 2 + 1):
            dmg += randint(1,4) % 4 + 1;
        second.hurt ( dmg );

@game_object
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

@game_object
class Mutilation (CInteraction):
    def performAction(self, first, second ):
        second.hurt ( first.getDmg() * 1.5 )

@game_object
class LethalPoison(CInteraction):
    def performAction(self,first, second ):
        pass

@game_object
class Bloodlash ( CInteraction):
    def performAction(self,first,second):
        second.hurt ( first.getDmg() * 1.5 )

@game_object
class Backstab(CInteraction):
    def performAction (self, first,second ):
        second.hurt ( first.getDmg() * 1.75 )

    def configureEffect(self,effect):
        if randint(1,5) == 0:
            return True
        else:
            return False

@game_object
class DeathStrike (CInteraction):
    def performAction(self, first, second ):
        second.hurt ( first.getDmg() * 2 )
        if  second.getHpRatio() < 20 :
            second.hurt ( first.getDmg() * 1.5 );

@game_object
class BloodThirst(CInteraction):
    def performAction ( first, second ):
        second.hurt ( first.getDmg() * 0.2 )
        first.healProc ( 20 )

@game_object
class AbyssalShadows(CInteraction):
    pass

@game_object
class Barrier(CInteraction):
    pass

@game_object
class Chloroform(CInteraction):
    pass

@game_object
class EndlessPain(CInteraction):
    pass

@game_object
class LethalPoison(CInteraction):
    pass

@game_object
class Mutilation(CInteraction):
    pass

@game_object
class Stunner(CInteraction):
    pass

@game_object
class ArmorOfEndlessWinter(CInteraction):
    def configureEffect(self,effect):
        stats =Stats();
        stats.setNumericProperty('armor', (getCaster().getStats().getNumericProperty('armor') * 0.75 ));
        setBonus ( stats );

@game_object
class Barrier ( CInteraction):
    def configureEffect(self,effect):
        firstgetCaster()
        stats =Stats();
        stats.setNumericProperty('armor', ( first.getStats().getNumericProperty('armor') * 0.5 ));
        stats.setNumericProperty('block', ( first.getStats().getNumericProperty('block') * 0.25 ));
        stats.setNumericProperty('damage', ( first.getStats().getNumericProperty('damage') * -0.5 ));
        setBonus ( stats );
