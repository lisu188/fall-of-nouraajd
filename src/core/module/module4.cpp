#include "core/CWrapper.h"

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
            .def("useAction", &CCreature::useAction);
    class_<CPlayer, bases<CCreature>, boost::noncopyable, std::shared_ptr<CPlayer>>("CPlayer")
            .def("addQuest", &CPlayer::addQuest);
    class_<CMonster, bases<CCreature>, boost::noncopyable, std::shared_ptr<CMonster>>("CMonster");
}