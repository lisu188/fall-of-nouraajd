from game import Damage
from game import Interaction
from random import randint

def Attack(first,second):
    dmg = first.getDmg()
    if dmg:
        second.hurt( dmg )
        weapon = first.getWeapon()
        if weapon:
            interaction = weapon.getInteraction()
            if interaction:
                interaction.onAction ( first, second );

def ElemStaff(first,second):
    damage=Damage()
    damage.setNumericProperty('fire',1)
    damage.setNumericProperty('frost',1)
    damage.setNumericProperty('thunder',1)
    second.hurt ( damage )

def DoubleAttack ( first,second ):
    Attack(first,second)
    Attack(first,second)

def SneakAttack ( first,second ):
    Attack( first, second );
    if randint(1,100) > ( 100 - second.getHpRatio()) and second.isAlive():
        Attack(second,first)

def Strike ( first, second ):
    if first.getWeapon():
        dmg = first.getDmg();
        if dmg:
            second.hurt ( dmg + first.getStats().getDamage())

def ChaosBlast (first, second ):
    damage=Damage()
    damage.setNumericProperty('fire',first.getMana() / 2)
    damage.setNumericProperty('thunder',first.getMana() / 2)
    second.hurt ( damage );

def Devour ( first, second ):
    crit = first.getStats().getNumericProperty('crit')
    first.getStats().setNumericProperty('crit', 0 )
    dmg = first.getDmg()
    if  dmg :
        second.hurt ( dmg )
        first.healProc ( ( dmg * 0.75 ) / first.getHpMax() * 100 )
    first.getStats().setNumericProperty('crit', crit )
