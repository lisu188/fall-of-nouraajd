#ifndef TILE_H
#define TILE_H

#include <QGraphicsPixmapItem>
#include"CMap.h"
#include <QJsonObject>
#include <map>
#include <string>
#include <functional>

class CTile : public CMapObject {
	Q_OBJECT
	Q_PROPERTY ( bool canStep READ canStep WRITE setCanStep USER true )
public:
	CTile();
	CTile ( const CTile &tile );
	virtual ~CTile();
	void moveTo ( int x, int y, int z, bool silent = false );
	Coords getCoords();
	void move ( int x, int y );
	void onStep();
	bool canStep() const;
	void setCanStep ( bool canStep );
	void addToScene ( CGameScene *scene );
	void removeFromScene ( CGameScene *scene );
	void setDraggable();
	virtual void onEnter();
	virtual void onMove();
	virtual bool canSave();
	void setMap ( CMap *map );

protected:
	bool step=false;
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );

private:
	void setXYZ ( int x, int y, int z );
	bool draggable = false;
	static std::map<QString, std::function<void() > > steps;
};
void RoadTile();
#endif // TILE_H
