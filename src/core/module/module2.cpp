#include "core/CWrapper.h"

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
    //TODO: panels
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

}