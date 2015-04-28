#pragma once
#include <QObject>
#include <unordered_map>
#include "Util.h"

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
	CGameEventCaused ( Type type,CGameObject *cause );
	CGameObject *getCause() const;
private:
	CGameObject *cause=0;
};

struct TriggerKey {
	TriggerKey ( QString name,CGameEvent::Type type ) :name ( name ),type ( type ) {}
	QString name;
	CGameEvent::Type type;
	bool operator== ( const TriggerKey &other ) const {
		return ( type == other.type && name == other.name );
	}
};

namespace std {
template<>
struct hash<TriggerKey> {
	std::hash<QString> stringHash;
	std::size_t operator() ( const TriggerKey &triggerKey ) const {
		using std::size_t;
		int hash=stringHash ( triggerKey.name );
		int type=static_cast<int> ( triggerKey.type ) *31;
		return ( size_t ) ( hash^type );
	}
};
}

class CEventHandler : public QObject {
	Q_OBJECT
public:
	CEventHandler ( CMap *map );
	void gameEvent ( CGameObject *mapObject , CGameEvent *event ) const;
private:
	std::unordered_map<TriggerKey, std::list<CTrigger*>> triggers;
	CMap*map=0;
};
