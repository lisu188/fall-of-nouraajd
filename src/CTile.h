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
public:
	CTile ( QString name, int x = 0, int y = 0, int z = 0 );
	CTile();
	CTile ( const CTile &tile );
	~CTile();
	void moveTo ( int x, int y, int z, bool silent = false );
	Coords getCoords();
	void move ( int x, int y );
	void onStep();
	bool canStep() const;
	static CTile *getTile ( QString type, int x, int y, int z );
	void addToScene ( CGameScene *scene );
	void removeFromScene ( CGameScene *scene );
	void loadFromJson ( QString name );
	void setDraggable();
	virtual void onEnter() {}
	virtual void onMove() {}
	virtual bool canSave();
	void setMap ( CMap *map );

protected:
	bool step;
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );

private:
	void setXYZ ( int x, int y, int z );
	bool draggable = false;
	static std::map<QString, std::function<void() > > steps;
	bool init = false;
};
void RoadTile();
#endif // TILE_H
