#ifndef TILE_H
#define TILE_H

#include <QGraphicsPixmapItem>
#include"CMap.h"
#include <lib/json/json.h>
#include <unordered_map>
#include <string>
#include <functional>

class Tile : public CMapObject {
	Q_OBJECT
public:
	Tile ( std::string name, int x = 0, int y = 0, int z = 0 );
	Tile ( QString name, int x = 0, int y = 0, int z = 0 );
	Tile();
	Tile ( const Tile &tile );
	~Tile();
	void moveTo ( int x, int y, int z, bool silent = false );
	Coords getCoords();
	void move ( int x, int y );
	void onStep();
	bool canStep() const;
	static Tile *getTile ( std::string type, int x, int y, int z );
	void addToScene ( CGameScene *scene );
	void removeFromScene ( CGameScene *scene );
	void loadFromJson ( std::string name );
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
	static std::unordered_map<std::string, std::function<void() > > steps;
	bool init = false;
};
void RoadTile();
#endif // TILE_H
