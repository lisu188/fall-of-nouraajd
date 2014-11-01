#pragma once
#include <QObject>
class CMap;

class CGameObject;
class CGameEvent:public QObject {
	Q_OBJECT
	Q_ENUMS ( Type )
public:
	enum Type {
		onEnter,onTurn,onCreate,onDestroy,onLeave,onUse,onEquip,onUnequip
	};
	CGameEvent ( Type type,CGameObject *cause=0 );
	Type getType() const;
	CGameObject *getCause() const;

private:
	const Type type;
	CGameObject *cause=0;
};

class CEventHandler : public QObject {
	Q_OBJECT
public:
	CEventHandler ( CMap *map );
	void gameEvent ( CGameEvent *event, CGameObject *mapObject ) const;
private:
	CMap*map=0;
};
