#ifndef TILE_H
#define TILE_H

#include <QGraphicsPixmapItem>
#include <src/map.h>
#include <lib/json/json.h>
#include <unordered_map>
#include <string>
#include <functional>

class Tile : public MapObject {
	Q_OBJECT
public:
	Tile ( std::string name, int x = 0, int y = 0, int z = 0 );
	Tile();
	Tile ( const Tile &tile );
	~Tile();
	void moveTo ( int x, int y, int z, bool silent = false );
	Coords getCoords();
	void move ( int x, int y );
	void onStep();
	bool canStep() const;
	static Tile *getTile ( std::string type, int x, int y, int z );
	void addToScene ( QGraphicsScene *scene );
	void removeFromScene ( QGraphicsScene *scene );
	void loadFromJson ( std::string name );
	void setDraggable();
	virtual void onEnter() {}
	virtual void onMove() {}
	virtual bool canSave();
	void setMap ( Map *map );

protected:
	bool step;
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );

private:
	void setXYZ ( int x, int y, int z );
	bool draggable = false;
	static std::unordered_map<std::string, std::function<void() > > steps;
	bool init = false;
};
Q_DECLARE_METATYPE ( Tile )
void RoadTile();
#endif // TILE_H
