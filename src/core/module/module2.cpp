/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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

#include "core/CGame.h"
#include "core/CWrapper.h"
#include "object/CDialog.h"

using namespace boost::python;

void initModule2() {


    class_<CBuilding, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CBuilding>>("CBuildingBase");
    class_<CWrapper<CBuilding>, bases<CBuilding>, boost::noncopyable, std::shared_ptr<CWrapper<CBuilding>>>("CBuilding")
            .def("onCreate", &CWrapper<CBuilding>::onCreate)
            .def("onTurn", &CWrapper<CBuilding>::onTurn)
            .def("onDestroy", &CWrapper<CBuilding>::onDestroy)
            .def("onLeave", &CWrapper<CBuilding>::onLeave)
            .def("onEnter", &CWrapper<CBuilding>::onEnter);

    class_<CEvent, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CEvent>>("CEventBase");
    class_<CWrapper<CEvent>, bases<CEvent>, boost::noncopyable, std::shared_ptr<CWrapper<CEvent>>>("CEvent")
            .def("onCreate", &CWrapper<CEvent>::onCreate)
            .def("onTurn", &CWrapper<CEvent>::onTurn)
            .def("onLeave", &CWrapper<CEvent>::onLeave)
            .def("onDestroy", &CWrapper<CEvent>::onDestroy)
            .def("onEnter", &CWrapper<CEvent>::onEnter);

    class_<CInteraction, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CInteraction>>("CInteractionBase")
            .def("onAction", &CInteraction::onAction);
    class_<CWrapper<CInteraction>, bases<CInteraction>, boost::noncopyable, std::shared_ptr<CWrapper<CInteraction>>>(
            "CInteraction")
            .def("performAction", &CWrapper<CInteraction>::performAction)
            .def("configureEffect", &CWrapper<CInteraction>::configureEffect);

    class_<Damage, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Damage>>("Damage");
    class_<Stats, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Stats>>("Stats");

    class_<CTile, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTile>>("CTileBase");
    class_<CWrapper<CTile>, bases<CTile>, boost::noncopyable, std::shared_ptr<CWrapper<CTile>>>("CTile").
            def("onStep", &CWrapper<CTile>::onStep);

    class_<CItem, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CItem>>("CItem");
    class_<CPotion, bases<CItem>, boost::noncopyable, std::shared_ptr<CPotion>>("CPotionBase");
    class_<CWrapper<CPotion>, bases<CPotion>, boost::noncopyable, std::shared_ptr<CWrapper<CPotion>>>("CPotion").
            def("onUse", &CWrapper<CPotion>::onUse);

    class_<CGameEvent, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CGameEvent>>("CGameEvent", no_init);
    class_<CGameEventCaused, bases<CGameEvent>, boost::noncopyable, std::shared_ptr<CGameEventCaused>>(
            "CGameEventCaused", no_init)
            .def("getCause", &CGameEventCaused::getCause);

    class_<CTrigger, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTrigger>>("CTriggerBase", no_init);
    class_<CWrapper<CTrigger>, bases<CTrigger>, boost::noncopyable, std::shared_ptr<CWrapper<CTrigger>>>("CTrigger")
            .def("trigger", &CWrapper<CTrigger>::trigger);

    class_<CQuest, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CQuest>>("CQuestBase", no_init);
    class_<CWrapper<CQuest>, bases<CQuest>, boost::noncopyable, std::shared_ptr<CWrapper<CQuest>>>("CQuest")
            .def("isCompleted", &CWrapper<CQuest>::isCompleted)
            .def("onComplete", &CWrapper<CQuest>::onComplete);

    class_<CDialog, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialog>>("CDialog", no_init);
    class_<CDialogOption, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialogOption>>("CDialogOption",
                                                                                                  no_init);
    class_<CDialogState, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CDialogState>>("CDialogState",
                                                                                                no_init);
}