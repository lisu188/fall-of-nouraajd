/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2020  Andrzej Lis

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
#include "core/CMap.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameQuestPanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/panel/CListView.h"

using namespace boost::python;

void initModule5() {
    class_<CGamePanel, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CGamePanel>>("CGamePanel",
                                                                                                    no_init);

    class_<CGameTradePanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameTradePanel>>("CGameTradePanel",
                                                                                                     no_init)
            .def("getMarket", &CGameTradePanel::getMarket);

    class_<CGameFightPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameFightPanel>>("CGameFightPanel",
                                                                                                     no_init);

    class_<CGameCharacterPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameCharacterPanel>>(
            "CGameCharacterPanel",
            no_init);

    class_<CGameDialogPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameDialogPanel>>(
            "CGameDialogPanel",
            no_init);

    class_<CGameInventoryPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameInventoryPanel>>(
            "CGameInventoryPanel",
            no_init);

    class_<CGameQuestPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameQuestPanel>>(
            "CGameQuestPanel",
            no_init);

    class_<CGameTextPanel, bases<CGamePanel>, boost::noncopyable, std::shared_ptr<CGameTextPanel>>(
            "CGameTextPanel",
            no_init);

    class_<CProxyTargetGraphicsObject, bases<CGameGraphicsObject>, boost::noncopyable, std::shared_ptr<CListView>>(
            "CProxyTargetGraphicsObject",
            no_init);

    class_<CListView, bases<CProxyTargetGraphicsObject>, boost::noncopyable, std::shared_ptr<CListView>>("CListView",
                                                                                                         no_init);

}