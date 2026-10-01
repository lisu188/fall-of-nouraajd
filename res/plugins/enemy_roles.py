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
            attack = None
            for action in first.getEffectiveInteractions():
                if action.getTypeId() == "Attack":
                    attack = action
                    break
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

    class EnemyPacketSignature(EnemySignature):
        def performSignature(self, first, second, attack):
            first.setObjectProperty("enemyRoleDamagePacket", self.getObjectProperty("roleDamage"))
            first.setStringProperty("enemyRoleDamageChannel", self.damageChannel)
            first.setBoolProperty("enemyRoleArcaneAttack", True)
            try:
                attack.performAction(first, second)
            finally:
                first.setBoolProperty("enemyRoleArcaneAttack", False)
                first.setStringProperty("enemyRoleDamageChannel", "")

    @register(context)
    class EnemyArcaneBolt(EnemyPacketSignature):
        damageChannel = "frost"

    @register(context)
    class EnemyOpeningStrike(EnemySignature):
        pass

    @register(context)
    class EnemyRitualHex(EnemyPacketSignature):
        damageChannel = "shadow"
