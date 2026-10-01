# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later


def load(self, context):
    from game import CEffect, CInteraction, register

    @register(context)
    class EnemyRoleEffect(CEffect):
        def onEffect(self):
            pass

    class EnemySignature(CInteraction):
        def performAction(self, first, second):
            if first.getBoolProperty("enemyRoleUsed"):
                return
            first.setBoolProperty("enemyRoleUsed", True)
            self.performSignature(first, second)

        def performSignature(self, first, second):
            pass

        def configureEffect(self, effect):
            caster = effect.getCaster()
            if caster.getBoolProperty("enemyRoleEffectApplied"):
                return False
            caster.setBoolProperty("enemyRoleEffectApplied", True)
            return True

    @register(context)
    class EnemyBrace(EnemySignature):
        pass

    @register(context)
    class EnemyArcaneBolt(EnemySignature):
        def performSignature(self, first, second):
            budget = max(0, first.getDmg())
            if not budget:
                return
            damage = first.getGame().createObject("CDamage")
            damage.setNumericProperty("normal", budget // 2)
            damage.setNumericProperty("frost", budget - budget // 2)
            second.hurt(damage)

    @register(context)
    class EnemyOpeningStrike(EnemySignature):
        def performSignature(self, first, second):
            budget = max(0, first.getDmg()) * 80 // 100
            if budget:
                second.hurt(budget)

    @register(context)
    class EnemyRitualHex(EnemySignature):
        pass
