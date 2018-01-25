#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "object/CObject.h"

class CMap;

class CTrigger;

class CGameObject;

class CGameEvent : public CGameObject {
V_META(CGameEvent, CGameObject, vstd::meta::empty())
public:
    class Type {
    public:
        static std::string onEnter;
        static std::string onTurn;
        static std::string onCreate;
        static std::string onDestroy;
        static std::string onLeave;
        static std::string onUse;
        static std::string onEquip;
        static std::string onUnequip;
    };

    CGameEvent();

    CGameEvent(std::string type);

    std::string getType() const;

private:
    const std::string type;
};

class CGameEventCaused : public CGameEvent {
V_META(CGameEventCaused, CGameEvent, vstd::meta::empty())
public:
    CGameEventCaused();

    CGameEventCaused(std::string type, std::shared_ptr<CGameObject> cause);

    std::shared_ptr<CGameObject> getCause() const;

private:
    std::shared_ptr<CGameObject> cause;
};

class CEventHandler : public CGameObject {
    typedef std::unordered_multimap<std::pair<std::string, std::string>, std::shared_ptr<CTrigger>> TriggerMap;
public:
    void gameEvent(std::shared_ptr<CMapObject> mapObject, std::shared_ptr<CGameEvent> event) const;

    void registerTrigger(std::shared_ptr<CTrigger> trigger);

    std::set<std::shared_ptr<CTrigger>> getTriggers();
private:
    TriggerMap triggers;
};
