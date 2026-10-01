# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from tests import test_python_callback_lifecycle as callback_lifecycle


class EnemyRoleRuntimeTest(unittest.TestCase):
    runChild = callback_lifecycle.PythonCallbackLifecycleTest.runChild

    def testExistingMonsterTemplatesUseOneSignatureAndSaveItsFlag(self):
        self.runChild("""
            import json
            from pathlib import Path
            import uuid
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
            game_map = instance.getMap()
            player = game_map.getPlayer()
            player.baseStats.stamina = 1000
            player.baseStats.block = 10
            player.setHp(player.getHpMax())
            cases = {'Gooby': 'enemyBrace', 'Pritz': 'enemyBrace', 'OctoBogz': 'enemyBrace',
                     'PritzMage': 'enemyArcaneBolt', 'GoblinThief': 'enemyOpeningStrike',
                     'Cultist': 'enemyRitualHex', 'CultLeader': 'enemyRitualHex'}
            for index, (template, signature_id) in enumerate(cases.items()):
                actor = instance.createObject(template)
                actor.name = 'roleRuntime' + str(index)
                actor.x, actor.y, actor.z = 3 + index, 5, 0
                game_map.addObject(actor)
                actor.setHp(max(1, actor.getHpMax() // 2))
                actor.setMana(0)
                baseline = game.jsonify(actor.baseStats)
                actions = {action.getTypeId(): action for action in actor.getEffectiveInteractions()}
                assert signature_id in actions, (template, actions)
                controller = actor.getFightController()
                effect = actions[signature_id].getObjectProperty('roleEffect')
                assert controller.control(actor, player), template
                assert actor.getBoolProperty('enemyRoleUsed'), template
                assert actions[signature_id].getObjectProperty('roleEffect') is None, template
                recipient = actor if actions[signature_id].getBoolProperty('selfTarget') else player
                assert any(active.name == effect.name for active in recipient.getEffects()), template
                assert effect.getTimeLeft() == 1 and effect.getVictim() == recipient, template
                assert not actor.getBoolProperty('enemyRoleArcaneAttack'), template
                assert actor.getMana() == 0, template
                assert controller.control(actor, player), template
                assert baseline == game.jsonify(actor.baseStats), template
                saved = json.loads(game.jsonify(actor))
                assert saved['properties']['enemyRoleUsed'], saved
            assert not player.getBoolProperty('enemyRoleUsed')
            slot = 'unit-enemy-roles-' + uuid.uuid4().hex
            provider = instance.getResourcesProvider()
            save_path = None
            try:
                assert game.CMapLoader.saveWithResult(game_map, slot)
                save_path = Path(provider.getPath('save/' + slot + '.json'))
                game.CGameLoader.loadSavedGame(instance, slot)
                loaded_map = instance.getMap()
                loaded_player = loaded_map.getPlayer()
                for index in range(len(cases)):
                    actor = loaded_map.getObjectByName('roleRuntime' + str(index))
                    assert actor.getBoolProperty('enemyRoleUsed'), index
                    assert actor.getBoolProperty('enemyRoleEffectApplied'), index
                    assert not actor.getBoolProperty('enemyRoleArcaneAttack'), index
                    signature = next(action for action in actor.getEffectiveInteractions() if action.getBoolProperty('enemySignature'))
                    assert not signature.hasProperty('roleEffect') or signature.getObjectProperty('roleEffect') is None, index
                    recipient = actor if signature.getBoolProperty('selfTarget') else loaded_player
                    linked = [effect for effect in recipient.getEffects() if effect.getCaster() == actor]
                    assert len(linked) == 1 and linked[0].getVictim() == recipient, index
                    assert actor.getFightController().control(actor, loaded_player), index
                    assert actor.getBoolProperty('enemyRoleUsed'), index
            finally:
                if save_path is not None:
                    save_path.unlink(missing_ok=True)
                    Path(str(save_path) + '.bak').unlink(missing_ok=True)
            print('existing monster signatures verified', flush=True)
            """)


if __name__ == "__main__":
    unittest.main()
