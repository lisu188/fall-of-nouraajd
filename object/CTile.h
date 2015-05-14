#pragma once
#include <QGraphicsPixmapItem>
#include <QJsonObject>
#include <map>
#include <string>
#include <functional>
#include "CMapObject.h"

class CGame;
class CCreature;
class CTile : public CGameObject {
	Q_OBJECT
	Q_PROPERTY ( bool canStep READ canStep WRITE setCanStep USER true )
public:
	CTile();
	virtual void onStep ( CCreature * );
	void move ( int x, int y, int z ) ;
	void moveTo ( int x,int y,int z );
	Coords getCoords();
	bool canStep() const;
	void setCanStep ( bool canStep );
	void addToScene ( CGame *scene );
	void removeFromScene ( CGame *scene );

	virtual ~CTile();
private:
	bool step=false;
	int posx=0,posy=0,posz=0;
	void setXYZ ( int x, int y, int z );
};
