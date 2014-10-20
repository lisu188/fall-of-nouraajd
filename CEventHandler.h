#pragma once

#include <QObject>

class CMapObject;
class CMap;

class CGameEvent:public QObject {
	Q_OBJECT
	Q_ENUMS ( CGameEvent )
public:
	enum Type {
		onEnter,onMove,onCreate,onDestroy,onLeave
	};
	CGameEvent ( Type type,CMapObject *cause=0 );
	Type getType() const;
	CMapObject *getCause() const;

private:
	const Type type;
	CMapObject *cause=0;
};

class CEventHandler : public QObject {
	Q_OBJECT
public:
	CEventHandler ( CMap *map );
	void gameEvent ( CGameEvent *event,CMapObject * mapObject ) const;
private:
	CMap*map=0;
};


