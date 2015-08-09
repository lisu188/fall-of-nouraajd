#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "object/CObject.h"

class CMap;
class CTrigger;

class CGameObject;

class CGameEvent:public QObject {
    Q_OBJECT
    Q_ENUMS ( Type )
public:
    enum Type {
        onEnter,onTurn,onCreate,onDestroy,onLeave,onUse,onEquip,onUnequip
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
    TriggerKey ( QString name,CGameEvent::Type type );
    QString name;
    CGameEvent::Type type;
    bool operator== ( const TriggerKey &other ) const;
};

namespace std {
    template<>
    struct hash<TriggerKey> {
        std::hash<QString> stringHash;
        std::size_t operator() ( const TriggerKey &triggerKey ) const;
    };
}

class CEventHandler {
    typedef std::unordered_multimap<TriggerKey, std::shared_ptr<CTrigger>> TriggerMap ;
public:
    void gameEvent ( std::shared_ptr<CMapObject> mapObject , std::shared_ptr<CGameEvent> event ) const;
    void registerTrigger ( QString name,QString type,std::shared_ptr<CTrigger > trigger );
private:
    TriggerMap triggers;
};
