#pragma once
#include <QGraphicsPixmapItem>
#include <QJsonObject>
#include <map>
#include <string>
#include <functional>
#include "CMapObject.h"

class CGameScene;
class CCreature;
class CTile : public CMapObject {
	Q_OBJECT
	Q_PROPERTY ( bool canStep READ canStep WRITE setCanStep USER true )
public:
	CTile();
	CTile ( const CTile &tile );
	virtual ~CTile();
    virtual void onStep ( CCreature * );
    virtual void move ( int x, int y, int z );
	Coords getCoords();
	bool canStep() const;
	void setCanStep ( bool canStep );
	void addToScene ( CGameScene *scene );
	void removeFromScene ( CGameScene *scene );
private:
    bool step=false;
	void setXYZ ( int x, int y, int z );
};
