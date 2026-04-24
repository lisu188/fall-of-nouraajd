# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
def load(self, context):
    from game import CInteraction
    from game import Damage
    from game import Stats
    from game import randint
    from game import register

    def is_cultist(creature):
        affiliation = creature.getStringProperty("affiliation")
        return affiliation in {"cult", "marumi"} or "Cult" in creature.getType()

    @register(context)
    class Attack(CInteraction):
        def performAction(self, first, second):
            dmg = first.getDmg()
            if dmg:
                second.hurt(dmg)
                weapon = first.getWeapon()
                if weapon:
                    inter = weapon.getInteraction()
                    if inter:
                        inter.onAction(first, second)

    @register(context)
    class ElemStaff(CInteraction):
        def performAction(self, first, second):
            damage = Damage()
            damage.setNumericProperty("fire", 1)
            damage.setNumericProperty("frost", 1)
            damage.setNumericProperty("thunder", 1)
            second.hurt(damage)

    @register(context)
    class DoubleAttack(CInteraction):
        def performAction(self, first, second):
            Attack().onAction(first, second)
            Attack().onAction(first, second)

    @register(context)
    class SneakAttack(Attack):
        def performAction(self, first, second):
            super(SneakAttack, self).performAction(first, second)
            if randint(1, 100) > (100 - second.getHpRatio()) and second.isAlive():
                super(SneakAttack, self).performAction(first, second)

    @register(context)
    class Strike(CInteraction):
        def performAction(self, first, second):
            if first.getWeapon():
                dmg = first.getDmg()
                if dmg:
                    second.hurt(dmg + first.getStats().getNumericProperty("damage"))

    @register(context)
    class ChaosBlast(CInteraction):
        def performAction(self, first, second):
            damage = Damage()
            damage.setNumericProperty("fire", first.getMana() // 2)
            damage.setNumericProperty("thunder", first.getMana() // 2)
            second.hurt(damage)

    @register(context)
    class Devour(CInteraction):
        def performAction(self, first, second):
            crit = first.getStats().getNumericProperty("crit")
            first.getStats().setNumericProperty("crit", 0)
            dmg = first.getDmg()
            if dmg:
                second.hurt(dmg)
                first.healProc((dmg * 75) // max(first.getHpMax(), 1))
            first.getStats().setNumericProperty("crit", crit)

    @register(context)
    class FrostBolt(CInteraction):
        def performAction(self, first, second):
            Attack().onAction(first, second)
            damage = Damage()
            intelligence = first.getStats().getNumericProperty("intelligence")
            damage.setNumericProperty("frost", intelligence * 75 // 100)
            second.hurt(damage)

    @register(context)
    class MagicMissile(CInteraction):
        def performAction(self, first, second):
            dmg = 0
            for _ in range(first.getLevel() // 2 + 1):
                dmg += randint(1, 4) % 4 + 1
            second.hurt(dmg)

    @register(context)
    class ShadowBolt(CInteraction):
        def performAction(self, first, second):
            damage = Damage()
            damage.setNumericProperty("shadow", int(first.getDmg() * 2.25))
            second.hurt(damage)

        def configureEffect(self, effect):
            if randint(1, 2) == 1:
                return True
            return False

    @register(context)
    class Mutilation(CInteraction):
        def performAction(self, first, second):
            second.hurt(int(first.getDmg() * 1.5))

    @register(context)
    class LethalPoison(CInteraction):
        def performAction(self, first, second):
            Attack().onAction(first, second)

    @register(context)
    class Bloodlash(CInteraction):
        def performAction(self, first, second):
            second.hurt(int(first.getDmg() * 1.5))

    @register(context)
    class Backstab(CInteraction):
        def performAction(self, first, second):
            second.hurt(int(first.getDmg() * 1.75))

        def configureEffect(self, effect):
            return randint(1, 5) == 1

    @register(context)
    class DeathStrike(CInteraction):
        def performAction(self, first, second):
            second.hurt(first.getDmg() * 2)
            if second.getHpRatio() < 20:
                second.hurt(int(first.getDmg() * 1.5))

    @register(context)
    class BloodThirst(CInteraction):
        def performAction(self, first, second):
            tmp_dmg = max(1, first.getDmg() * 20 // 100)
            second.hurt(tmp_dmg)
            first.heal(tmp_dmg)

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
    class Stunner(CInteraction):
        pass

    @register(context)
    class ArmorOfEndlessWinter(CInteraction):
        def configureEffect(self, effect):
            caster = effect.getCaster()
            if not caster:
                return False
            stats = Stats()
            stats.setNumericProperty("armor", caster.getStats().getNumericProperty("armor") * 75 // 100)
            effect.setBonus(stats)
            return True

    @register(context)
    class ExposeCorruption(CInteraction):
        def performAction(self, first, second):
            Attack().onAction(first, second)
            damage = Damage()
            clues = first.getNumericProperty("inquisitor_clues")
            base = first.getStats().getNumericProperty("intelligence") // 2 + first.getLevel()
            if is_cultist(second):
                base += 3 + clues * 2
            damage.setNumericProperty("fire", max(1, base))
            second.hurt(damage)

        def configureEffect(self, effect):
            caster = effect.getCaster()
            if not caster:
                return False
            clues = caster.getNumericProperty("inquisitor_clues")
            stats = Stats()
            stats.setNumericProperty("armor", -(2 + clues * 2))
            stats.setNumericProperty("block", -(2 + caster.getLevel() // 2))
            effect.setBonus(stats)
            effect.setNumericProperty("inquisitor_clues", clues)
            return True

    @register(context)
    class SanctifiedWard(CInteraction):
        def performAction(self, first, second):
            first.healProc(4 + first.getLevel())

        def configureEffect(self, effect):
            caster = effect.getCaster()
            if not caster:
                return False
            clues = caster.getNumericProperty("inquisitor_clues")
            stats = Stats()
            stats.setNumericProperty("armor", 4 + caster.getLevel() + clues)
            stats.setNumericProperty("normalResist", 3 + clues * 2)
            stats.setNumericProperty("hit", 2 + clues)
            effect.setBonus(stats)
            effect.setNumericProperty("inquisitor_clues", clues)
            return True

    @register(context)
    class WayfarersStride(CInteraction):
        def performAction(self, first, second):
            first.addManaProc(12)

        def configureEffect(self, effect):
            caster = effect.getCaster()
            if not caster:
                return False
            routes = caster.getNumericProperty("wayfarer_routes")
            stats = Stats()
            stats.setNumericProperty("agility", 2 + routes + caster.getLevel() // 3)
            stats.setNumericProperty("block", 4 + routes * 2)
            stats.setNumericProperty("hit", 3 + routes)
            effect.setBonus(stats)
            effect.setNumericProperty("wayfarer_routes", routes)
            return True

    @register(context)
    class SmugglersMark(CInteraction):
        def performAction(self, first, second):
            damage = Damage()
            routes = first.getNumericProperty("wayfarer_routes")
            damage.setNumericProperty("normal", max(1, first.getStats().getNumericProperty("agility") // 2 + routes))
            second.hurt(damage)

        def configureEffect(self, effect):
            caster = effect.getCaster()
            if not caster:
                return False
            routes = caster.getNumericProperty("wayfarer_routes")
            stats = Stats()
            stats.setNumericProperty("block", -(3 + routes * 2))
            stats.setNumericProperty("hit", -(2 + caster.getLevel() // 3))
            effect.setBonus(stats)
            effect.setNumericProperty("wayfarer_routes", routes)
            return True
