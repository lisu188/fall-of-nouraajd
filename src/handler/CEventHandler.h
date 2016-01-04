#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "object/CObject.h"

class CMap;

class CTrigger;

class CGameObject;

class CGameEvent : public QObject {

    Q_ENUMS ( Type )
public:
    enum Type {
        onEnter, onTurn, onCreate, onDestroy, onLeave, onUse, onEquip, onUnequip
    };

    CGameEvent ( Type type );

    Type getType() const;

private:
    const Type type;
};

class CGameEventCaused : public CGameEvent {
public:
    CGameEventCaused ( Type type, std::shared_ptr<CGameObject> cause );

    std::shared_ptr<CGameObject> getCause() const;

private:
    std::shared_ptr<CGameObject> cause;
};

struct TriggerKey {
    TriggerKey ( std::string name, CGameEvent::Type type );

    std::string name;
    CGameEvent::Type type;

    bool operator== ( const TriggerKey &other ) const;
};

namespace std {
    template<>
    struct hash<TriggerKey> {
        std::size_t operator() ( const TriggerKey &triggerKey ) const;
    };
}

class CEventHandler {
    typedef std::unordered_multimap<TriggerKey, std::shared_ptr<CTrigger>> TriggerMap;
public:
    void gameEvent ( std::shared_ptr<CMapObject> mapObject, std::shared_ptr<CGameEvent> event ) const;

    void registerTrigger ( std::string name, std::string type, std::shared_ptr<CTrigger> trigger );

private:
    TriggerMap triggers;
};
