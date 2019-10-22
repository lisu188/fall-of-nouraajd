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
#include "core/CList.h"

using namespace boost::python;

void initModule4() {


    class_<CEffect, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEffect>>("CEffectBase")
            .def("getBonus", &CEffect::getBonus)
            .def("setBonus", &CEffect::setBonus)
            .def("getCaster", &CEffect::getCaster)
            .def("getVictim", &CEffect::getVictim)
            .def("getTimeLeft", &CEffect::getTimeLeft);
    class_<CWrapper<CEffect>, bases<CEffect>, boost::noncopyable, std::shared_ptr<CWrapper<CEffect>>>("CEffect")
            .def("onEffect", &CWrapper<CEffect>::onEffect);


    class_<CWeapon, bases<CItem>, boost::noncopyable, std::shared_ptr<CWeapon>>("CWeapon")
            .def("getInteraction", &CWeapon::getInteraction);

    void ( CCreature::*hurtInt )(int) = &CCreature::hurt;
    void ( CCreature::*hurtFloat )(float) = &CCreature::hurt;
    void ( CCreature::*hurtDmg )(std::shared_ptr<Damage>) = &CCreature::hurt;
    void ( CCreature::*addItem )(std::string) = &CCreature::addItem;
    bool ( CCreature::*hasItem )(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::hasItem;
    void ( CCreature::*removeItem )(std::function<bool(std::shared_ptr<CItem>)>,bool) = &CCreature::removeItem;
    void ( CCreature::*removeQuestItem )(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::removeQuestItem;
    class_<CCreature, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CCreature>>("CCreature", no_init)
            .def("getDmg", &CCreature::getDmg)
            .def("hurt", hurtInt)
            .def("hurt", hurtDmg)
            .def("hurt", hurtFloat)
            .def("getWeapon", &CCreature::getWeapon)
            .def("getHpRatio", &CCreature::getHpRatio)
            .def("isAlive", &CCreature::isAlive)
            .def("getMana", &CCreature::getMana)
            .def("healProc", &CCreature::healProc)
            .def("heal", &CCreature::heal)
            .def("getHpMax", &CCreature::getHpMax)
            .def("getLevel", &CCreature::getLevel)
            .def("getStats", &CCreature::getStats)
            .def("addManaProc", &CCreature::addManaProc)
            .def("isPlayer", &CCreature::isPlayer)
            .def("addExp", &CCreature::addExp)
            .def("useAction", &CCreature::useAction)
            .def("hasItem", hasItem)
            .def("addItem", addItem)
            .def("removeItem", removeItem)
            .def("removeQuestItem", removeQuestItem);
    class_<CPlayer, bases<CCreature>, boost::noncopyable, std::shared_ptr<CPlayer>>("CPlayer")
            .def("addQuest", &CPlayer::addQuest);
    class_<CMonster, bases<CCreature>, boost::noncopyable, std::shared_ptr<CMonster>>("CMonster");

    class_<CListString, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CListString>>("CListString")
            .def("addValue", &CListString::addValue);
}