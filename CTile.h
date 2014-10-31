#pragma once
#include <QGraphicsPixmapItem>
#include <QJsonObject>
#include <map>
#include <string>
#include <functional>
#include "CMapObject.h"

class CGameScene;
class CCreature;
class CTile : public CGameObject,public Steppable {
	Q_OBJECT
	Q_PROPERTY ( bool canStep READ canStep WRITE setCanStep USER true )
public:
	CTile();
	CTile ( const CTile &tile );
	virtual void onStep ( CGameEvent * ) override;
	void move ( int x, int y, int z ) ;
	void moveTo ( int x,int y,int z );
	Coords getCoords();
	bool canStep() const;
	void setCanStep ( bool canStep );
	void addToScene ( CGameScene *scene );
	void removeFromScene ( CGameScene *scene );

	virtual ~CTile();
private:
	bool step=false;
	int posx=0,posy=0,posz=0;
	void setXYZ ( int x, int y, int z );
};
