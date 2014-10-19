#pragma once

#include <QObject>

class CMapObject;
class CMap;
class CEventHandler : public QObject {
	Q_OBJECT
	Q_ENUMS ( GameEvent )
public:
	enum GameEvent {
		onEnter,onMove,onCreate,onDestroy,onLeave
	};
	CEventHandler ( CMap *map );
	void gameEvent ( GameEvent type,CMapObject * source );
private:
	void onEnterEvent ( CMapObject *mapObject );
	void onMoveEvent ( CMapObject *mapObject );
	void onDestroyEvent ( CMapObject *mapObject );
	void onCreateEvent ( CMapObject *mapObject );
	void onLeaveEvent ( CMapObject *mapObject );
	CMap*map=0;
};

typedef CEventHandler::GameEvent GameEvent;

