# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from tests import test_python_callback_lifecycle as callback_lifecycle


class OctobogzRuntimeTest(unittest.TestCase):
    runChild = callback_lifecycle.PythonCallbackLifecycleTest.runChild

    def testNativeActorDeathsPartialSaveAndLivingRecoveryPreserveIdentityAndRewardOnce(self):
        self.runChild("""
            import json
            from pathlib import Path
            import uuid
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'nouraajd', 'Warrior')
            game_map = instance.getMap()
            player = game_map.getPlayer()
            for _ in range(3): loop.run()
            director = instance.createObject('OctobogzHuntDirector')
            state = lambda: json.loads(game_map.getStringProperty('octobogzHuntRegistry'))
            game_map.removeObjectByName('cave2')
            assert not game_map.getBoolProperty('OCTOBOGZ_SLAIN')
            assert not game_map.getBoolProperty('octobogzHuntCleared')
            director.start(game_map)
            scout = game_map.getObjectByName(state()['slots']['scout']['name'])
            assert scout.getController().getTarget() == 'cave2' and scout.getController().getDistance() == 10
            scout.setHp(0)
            game_map.removeObject(scout)
            for _ in range(3): loop.run()
            assert state()['stage'] == 'brood'
            alpha_name = state()['slots']['alpha']['name']
            alpha = game_map.getObjectByName(alpha_name)
            assert json.loads(game.jsonify(alpha))['properties']['creatureClass']['properties']['combatRole'] == 'brute'
            assert {'Attack', 'octobogzCharge', 'octobogzShadowPulse'} <= {
                action.getTypeId() for action in alpha.getActions()}
            assert alpha.getController().getTarget() == 'cave2' and alpha.getController().getDistance() == 10
            alpha.setHp(9)
            alpha.setMana(6)
            assert alpha.getFightController().control(alpha, player)
            assert alpha.getStringProperty('octobogzCombatPhase') == 'charged'
            assert not alpha.getBoolProperty('enemyRoleUsed')
            save_slot = 'unit-octobogz-' + uuid.uuid4().hex
            save_path = None
            try:
                assert game.CMapLoader.saveWithResult(game_map, save_slot)
                save_path = Path(instance.getResourcesProvider().getPath('save/' + save_slot + '.json'))
                game.CGameLoader.loadSavedGame(instance, save_slot)
                game_map = instance.getMap()
                player = game_map.getPlayer()
                for _ in range(3): loop.run()
                alpha = game_map.getObjectByName(alpha_name)
                assert alpha.getHp() == 9 and alpha.getMana() == 6
                assert alpha.getStringProperty('octobogzCombatPhase') == 'charged'
                director = instance.createObject('OctobogzHuntDirector')
                director.synchronize(game_map)
                assert game_map.getObjectByName(alpha_name) == alpha
                game_map.removeObject(alpha)
                assert state()['slots']['alpha']['status'] == 'pending'
                assert not game_map.getBoolProperty('octobogzHuntCleared')
                for _ in range(3): loop.run()
                restored = game_map.getObjectByName(alpha_name)
                assert restored is not None and restored != alpha
                assert restored.getHp() == 9 and restored.getMana() == 6
                assert restored.getController().getTarget() == 'cave2' and restored.getController().getDistance() == 10
                assert restored.getStringProperty('octobogzCombatPhase') == 'charged'
                assert len([obj for obj in game_map.getObjects() if obj.getName() == alpha_name]) == 1
                pulse = next(action for action in restored.getActions() if action.getTypeId() == 'octobogzShadowPulse')
                effect = pulse.getObjectProperty('roleEffect')
                before_shadow = player.getStats().getNumericProperty('shadowResist')
                assert restored.getFightController().control(restored, player)
                assert restored.getMana() == 1 and restored.getBoolProperty('octobogzPulseUsed')
                assert restored.getBoolProperty('octobogzPulseEffectApplied')
                assert pulse.getObjectProperty('roleEffect') is None
                assert effect.getCaster() == restored and effect.getVictim() == player
                assert effect in player.getEffects() and effect.getTimeLeft() == 1
                assert player.getStats().getNumericProperty('shadowResist') == before_shadow - 1
                assert not restored.getBoolProperty('enemyRoleArcaneAttack')
                assert restored.getStringProperty('enemyRoleDamageChannel') == ''
                pulse.onAction(restored, player)
                assert restored.getMana() == 1 and len([active for active in player.getEffects() if active == effect]) == 1
                assert game.CMapLoader.saveWithResult(game_map, save_slot)
                game.CGameLoader.loadSavedGame(instance, save_slot)
                game_map = instance.getMap()
                player = game_map.getPlayer()
                for _ in range(3): loop.run()
                restored = game_map.getObjectByName(alpha_name)
                assert restored.getBoolProperty('octobogzPulseUsed') and restored.getMana() == 1
                pulse = next(action for action in restored.getActions() if action.getTypeId() == 'octobogzShadowPulse')
                assert json.loads(game.jsonify(pulse))['properties'].get('roleEffect') is None
                linked = [active for active in player.getEffects() if active.getCaster() == restored]
                assert len(linked) == 1 and linked[0].getVictim() == player and linked[0].getTimeLeft() == 1
                director = instance.createObject('OctobogzHuntDirector')
                restored.setHp(0)
                game_map.removeObject(restored)
                for _ in range(3): loop.run()
                assert not game_map.getBoolProperty('OCTOBOGZ_SLAIN')
                brood = game_map.getObjectByName(state()['slots']['brood']['name'])
                brood.setHp(0)
                game_map.removeObject(brood)
                for _ in range(3): loop.run()
                assert state()['stage'] == 'cleared'
                assert game_map.getBoolProperty('OCTOBOGZ_SLAIN')
                assert game_map.getObjectByName('cave2') is None
                before_gold, before_blades = player.getGold(), player.countItems('ShadowBlade')
                dialog = instance.createObject('dialog')
                dialog.accept_quest()
                assert player.getGold() == before_gold + 1000
                assert player.countItems('ShadowBlade') == before_blades + 1
                assert any(quest.getTypeId() == 'octoBogzQuest' for quest in player.getCompletedQuests())
                dialog.accept_quest()
                director.start(game_map)
                assert player.getGold() == before_gold + 1000
                assert player.countItems('ShadowBlade') == before_blades + 1
            finally:
                if save_path is not None:
                    save_path.unlink(missing_ok=True)
                    Path(str(save_path) + '.bak').unlink(missing_ok=True)
            print('native hunt partial save, recovery and late reward verified', flush=True)
            """)

    def testNativeLegacyAdoptionAddsActionsWithoutChangingHealthOrExtraActors(self):
        self.runChild("""
            import json
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'nouraajd', 'Sorcerer')
            game_map = instance.getMap()
            for _ in range(3): loop.run()
            game_map.setStringProperty('octobogzHuntRegistry', '')
            legacy = []
            for index in range(6):
                actor = instance.createObject('OctoBogz')
                actor.name = 'legacyHunt' + str(index)
                actor.setStringProperty('affiliation', 'bogz')
                actor.relocateWithoutMoveHooks(game.Coords(165, 21, 0))
                game_map.addObject(actor)
                actor.setHp(11 + index)
                actor.setMana(3 + index)
                legacy.append(actor)
            director = instance.createObject('OctobogzHuntDirector')
            director.synchronize(game_map)
            registry = json.loads(game_map.getStringProperty('octobogzHuntRegistry'))
            assert registry['stage'] == 'brood'
            for index, slot in enumerate(('scout', 'brood', 'alpha')):
                record = registry['slots'][slot]
                assert record['name'] == legacy[index].getName()
                assert game_map.getObjectByName(record['name']) == legacy[index]
                assert legacy[index].getHp() == 11 + index and legacy[index].getMana() == 3 + index
            for actor in legacy[3:]:
                assert not actor.getStringProperty('octobogzHuntSlot')
                assert game_map.getObjectByName(actor.getName()) == actor
            alpha = legacy[2]
            before_actions = len(alpha.getActions())
            alpha.addAction(instance.createObject('octobogzShadowPulse'))
            assert len(alpha.getActions()) == before_actions
            print('native hunt adoption and addAction binding verified', flush=True)
            """)


if __name__ == "__main__":
    unittest.main()
