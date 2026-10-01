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
            attack = next(
                (action for action in first.getEffectiveInteractions() if action.getTypeId() == "Attack"), None
            )
            if attack is None:
                return
            first.setBoolProperty("enemyRoleUsed", True)
            self.performSignature(first, second, attack)
            effect = self.getObjectProperty("roleEffect")
            recipient = first if self.getBoolProperty("selfTarget") else second
            if not first.getBoolProperty("enemyRoleEffectApplied") and recipient.isAlive():
                first.setBoolProperty("enemyRoleEffectApplied", True)
                self.setObjectProperty("roleEffect", None)
                effect.setCaster(first)
                effect.setVictim(recipient)
                recipient.addEffect(effect)

        def performSignature(self, first, second, attack):
            attack.performAction(first, second)

    @register(context)
    class EnemyBrace(EnemySignature):
        pass

    @register(context)
    class EnemyArcaneBolt(EnemySignature):
        def performSignature(self, first, second, attack):
            first.setObjectProperty("enemyRoleDamagePacket", self.getObjectProperty("roleDamage"))
            first.setBoolProperty("enemyRoleArcaneAttack", True)
            try:
                attack.performAction(first, second)
            finally:
                first.setBoolProperty("enemyRoleArcaneAttack", False)

    @register(context)
    class EnemyOpeningStrike(EnemySignature):
        pass

    @register(context)
    class EnemyRitualHex(EnemySignature):
        pass
