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
    from game import CTag
    from game import CEffect
    from game import Damage
    from game import register

    def is_cultist(creature):
        affiliation = creature.getStringProperty("affiliation")
        return affiliation in {"cult", "marumi"} or "Cult" in creature.getType()

    @register(context)
    class Stun(CEffect):
        def onEffect(self):
            pass

    @register(context)
    class EndlessPainEffect(CEffect):
        def onEffect(self):
            self.getVictim().hurt(self.getCaster().getDmg() * 15 // 100)

    @register(context)
    class AbyssalShadowsEffect(CEffect):
        def onEffect(self):
            dmg = Damage()
            if self.getTimeLeft() > 1:
                dmg.setNumericProperty("shadow", self.getCaster().getDmg() * 45 // 100)
            else:
                dmg.setNumericProperty("shadow", self.getCaster().getDmg())
            self.getVictim().hurt(dmg)

    @register(context)
    class ArmorOfEndlessWinterEffect(CEffect):
        def onEffect(self):
            self.getVictim().healProc(20)

    @register(context)
    class MutilationEffect(CEffect):
        def onEffect(self):
            self.getVictim().hurt(self.getCaster().getStats().getNumericProperty("agility") // 4)

    @register(context)
    class LethalPoisonEffect(CEffect):
        def onEffect(self):
            self.getVictim().hurt(self.getCaster().getDmg() * 4 // 6)

    @register(context)
    class BloodlashEffect(CEffect):
        def onEffect(self):
            self.getVictim().hurt(int(self.getCaster().getDmg() * 0.75))

    @register(context)
    class ChloroformEffect(CEffect):
        def onEffect(self):
            if self.getVictim().getHpRatio() > 25:
                self.removeTag(CTag.STUN)
            else:
                self.addTag(CTag.STUN)

    @register(context)
    class BarrierEffect(CEffect):
        def onEffect(self):
            pass

    @register(context)
    class ExposeCorruptionEffect(CEffect):
        def onEffect(self):
            caster = self.getCaster()
            victim = self.getVictim()
            clues = self.getNumericProperty("inquisitor_clues")
            base = max(1, caster.getStats().getNumericProperty("intelligence") // 3 + caster.getLevel())
            if is_cultist(victim):
                base += 2 + clues * 2
            damage = Damage()
            damage.setNumericProperty("fire", base)
            victim.hurt(damage)

    @register(context)
    class SanctifiedWardEffect(CEffect):
        def onEffect(self):
            clues = self.getNumericProperty("inquisitor_clues")
            self.getVictim().healProc(3 + clues * 2)
            self.getVictim().addManaProc(4 + clues)

    @register(context)
    class WayfarersStrideEffect(CEffect):
        def onEffect(self):
            routes = self.getNumericProperty("wayfarer_routes")
            self.getVictim().addManaProc(6 + routes * 2)
            self.getVictim().healProc(2 + routes)

    @register(context)
    class SmugglersMarkEffect(CEffect):
        def onEffect(self):
            caster = self.getCaster()
            routes = self.getNumericProperty("wayfarer_routes")
            damage = Damage()
            damage.setNumericProperty(
                "normal",
                max(1, caster.getStats().getNumericProperty("agility") // 3 + caster.getLevel() // 2 + routes),
            )
            self.getVictim().hurt(damage)
