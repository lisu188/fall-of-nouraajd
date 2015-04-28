#pragma once
#include <QObject>

class CGameObject;
class CMap;

class CClickAction {
public:
	virtual void onClickAction ( CGameObject *object ) =0;
};

class CMouseHandler : public QObject {
	Q_OBJECT
public:
	CMouseHandler ( CMap*map );
	void handleClick ( CGameObject *object );
private:
	CClickAction *getClickAction ( CGameObject *object );
};
