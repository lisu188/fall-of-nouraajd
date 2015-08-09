from game import Damage
from game import Stats
from game import CInteraction
from game import randint
from game import register

def load(context):
    @register(context)
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

    @register(context)
    class ElemStaff(CInteraction):
        def performAction(self,first,second):
            damage=Damage()
            damage.setNumericProperty('fire',1)
            damage.setNumericProperty('frost',1)
            damage.setNumericProperty('thunder',1)
            second.hurt ( damage )

    @register(context)
    class DoubleAttack(CInteraction):
        def performAction ( self,first,second ):
            Attack().onAction(first, second)
            Attack().onAction(first, second)

    @register(context)
    class SneakAttack(Attack):
        def performAction( self,first,second ):
            super(SneakAttack,self).performAction(first, second)
            if randint(1,100) > ( 100 - second.getHpRatio()) and second.isAlive():
                super(SneakAttack,self).performAction(first, second)

    @register(context)
    class Strike(CInteraction):
        def performAction ( self,first, second ):
            if first.getWeapon():
                dmg = first.getDmg();
                if dmg:
                    second.hurt ( dmg + first.getStats().getNumericProperty('damage'))

    @register(context)
    class ChaosBlast(CInteraction):
        def performAction (self,first, second ):
            damage=Damage()
            damage.setNumericProperty('fire',first.getMana() // 2)
            damage.setNumericProperty('thunder',first.getMana() // 2)
            second.hurt ( damage );

    @register(context)
    class Devour(CInteraction):
        def performAction ( self,first, second ):
            crit = first.getStats().getNumericProperty('crit')
            first.getStats().setNumericProperty('crit', 0 )
            dmg = first.getDmg()
            if dmg :
                second.hurt ( dmg )
                first.healProc ( ( dmg * 0.75 ) // first.getHpMax() * 100 )
            first.getStats().setNumericProperty('crit', crit )

    @register(context)
    class FrostBolt(CInteraction):
        def performAction (self, first, second ):
            Attack().onAction( first, second )
            damage=Damage()
            damage.setNumericProperty('frost', first.getStats().getNumericProperty('intelligence') * 75.0 // 100.0)
            second.hurt ( damage )

    @register(context)
    class MagicMissile(CInteraction):
        def performAction (self, first, second ):
            dmg = 0;
            for i in range(first.getLevel() // 2 + 1):
                dmg += randint(1,4) % 4 + 1;
            second.hurt ( dmg );

    @register(context)
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

    @register(context)
    class Mutilation (CInteraction):
        def performAction(self, first, second ):
            second.hurt ( first.getDmg() * 1.5 )

    @register(context)
    class LethalPoison(CInteraction):
        def performAction(self,first, second ):
            pass

    @register(context)
    class Bloodlash ( CInteraction):
        def performAction(self,first,second):
            second.hurt ( first.getDmg() * 1.5 )

    @register(context)
    class Backstab(CInteraction):
        def performAction (self, first,second ):
            second.hurt ( first.getDmg() * 1.75 )

        def configureEffect(self,effect):
            if randint(1,5) == 0:
                return True
            else:
                return False

    @register(context)
    class DeathStrike (CInteraction):
        def performAction(self, first, second ):
            second.hurt ( first.getDmg() * 2 )
            if second.getHpRatio() < 20 :
                second.hurt ( first.getDmg() * 1.5 );

    @register(context)
    class BloodThirst(CInteraction):
        def performAction ( first, second ):
            second.hurt ( first.getDmg() * 0.2 )
            first.healProc ( 20 )

    @register(context)
    class AbyssalShadows(CInteraction):
        pass

    @register(context)
    class Barrier(CInteraction):
        pass

    @register(context)
    class Chloroform(CInteraction):
        pass

    @register(context)
    class EndlessPain(CInteraction):
        pass

    @register(context)
    class LethalPoison(CInteraction):
        pass

    @register(context)
    class Mutilation(CInteraction):
        pass

    @register(context)
    class Stunner(CInteraction):
        pass

    @register(context)
    class ArmorOfEndlessWinter(CInteraction):
        def configureEffect(self,effect):
            stats =Stats();
            stats.setNumericProperty('armor', (getCaster().getStats().getNumericProperty('armor') * 0.75 ));
            setBonus ( stats );

    @register(context)
    class Barrier ( CInteraction):
        def configureEffect(self,effect):
            firstgetCaster()
            stats =Stats();
            stats.setNumericProperty('armor', ( first.getStats().getNumericProperty('armor') * 0.5 ));
            stats.setNumericProperty('block', ( first.getStats().getNumericProperty('block') * 0.25 ));
            stats.setNumericProperty('damage', ( first.getStats().getNumericProperty('damage') * -0.5 ));
            setBonus ( stats );
