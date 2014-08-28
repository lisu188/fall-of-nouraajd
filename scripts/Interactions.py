from _Game import Damage
from _Game import Interaction
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
    damage.fire=1
    damage.frost=1
    damage.thunder=1
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

