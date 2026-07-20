/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/panel/CCreatureView.h"
#include "gui/panel/CGameCampaignPanel.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGameLootPanel.h"
#include "gui/panel/CGamePanel.h"
#include "gui/panel/CGameQuestPanel.h"
#include "gui/panel/CGameQuestionPanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "gui/panel/CListView.h"

namespace type_registration {
void registerGuiPanelTypes() {
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameTextPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameInventoryPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameTradePanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameFightPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameQuestPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameCharacterPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameQuestionPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameCampaignPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameDialogPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CGameLootPanel, CGamePanel, CGameGraphicsObject, CGameObject>();

    CTypes::register_type<CProxyTargetGraphicsObject, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CListView, CProxyTargetGraphicsObject, CGameGraphicsObject, CGameObject>();
    CTypes::register_type<CCreatureView, CProxyTargetGraphicsObject, CGameGraphicsObject, CGameObject>();
}
} // namespace type_registration
