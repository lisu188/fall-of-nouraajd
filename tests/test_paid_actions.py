# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest


class PaidActionRuntimeTest(unittest.TestCase):
    def test_python_refund_callback_runs_only_after_a_paid_cast(self):
        try:
            import game
        except ImportError as exc:
            self.skipTest(f"compiled game module unavailable: {exc}")

        calls = {"performed": 0, "queried": 0}

        class RefundProbe(game.CInteraction):
            def performAction(self, first, second):
                calls["performed"] += 1

            def getCommittedManaRefund(self, caster):
                calls["queried"] += 1
                return 3

        engine = game.CGameLoader.loadGame()
        actor = engine.createObject("Warrior")
        action = RefundProbe()
        action.setNumericProperty("manaCost", 17)
        action.effect = engine.createObject("BarrierEffect")
        action.setBoolProperty("selfTarget", True)
        actor.setMana(16)
        action.onAction(actor, actor)
        self.assertEqual(16, actor.getMana())
        self.assertEqual({"performed": 0, "queried": 0}, calls)
        self.assertEqual(0, len(actor.getEffects()))
        actor.setMana(40)
        action.onAction(actor, actor)
        action.onAction(actor, actor)
        self.assertEqual(12, actor.getMana())
        self.assertEqual({"performed": 2, "queried": 2}, calls)
        action.getCommittedManaRefund(actor)
        action.performAction(actor, actor)
        self.assertEqual(12, actor.getMana(), "metadata and direct action callbacks cannot restore mana")

    def test_python_zero_and_oversized_refunds_do_not_create_mana(self):
        try:
            import game
        except ImportError as exc:
            self.skipTest(f"compiled game module unavailable: {exc}")

        refund_amount = [100]

        class RefundProbe(game.CInteraction):
            def getCommittedManaRefund(self, caster):
                return refund_amount[0]

        engine = game.CGameLoader.loadGame()
        actor = engine.createObject("Warrior")
        action = RefundProbe()
        action.setNumericProperty("manaCost", 17)
        actor.setMana(17)
        action.onAction(actor, actor)
        self.assertEqual(17, actor.getMana())
        refund_amount[0] = -1
        action.onAction(actor, actor)
        self.assertEqual(0, actor.getMana())

    def test_failed_refund_callback_keeps_the_paid_cost(self):
        try:
            import game
        except ImportError as exc:
            self.skipTest(f"compiled game module unavailable: {exc}")

        class BrokenRefund(game.CInteraction):
            def getCommittedManaRefund(self, caster):
                raise RuntimeError("refund probe failure")

        engine = game.CGameLoader.loadGame()
        actor = engine.createObject("Warrior")
        action = BrokenRefund()
        action.setNumericProperty("manaCost", 17)
        actor.setMana(17)
        action.onAction(actor, actor)
        self.assertEqual(0, actor.getMana())
        action.setNumericProperty("manaCost", 0)
        refund_amount[0] = 100
        action.onAction(actor, actor)
        self.assertEqual(0, actor.getMana())


if __name__ == "__main__":
    unittest.main()
