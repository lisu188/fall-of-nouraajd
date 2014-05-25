#ifndef MAP_H
#define MAP_H

#include <list>
#include <QTimer>
#include <QObject>
#include <qgraphicsitemanimation.h>
#include <QTimeLine>
#include <src/animation/animation.h>
#include <src/animation/animatedobject.h>
#include <unordered_map>
#include <set>
#include <lib/json/json.h>
#include <lib/tmx/TmxMap.h>

class MapObject;
class Tile;
class Player;
class Coords
{
public:
    Coords();
    Coords(int x, int y, int z);
    int x, y, z;
    bool operator==(const Coords &other) const;
    bool operator<(const Coords &other) const;
    int getDist(Coords a);
};

struct CoordsHasher {
    std::size_t operator()(const Coords& coords) const;
};

class Map : public std::unordered_map<Coords, std::string, CoordsHasher>
{
public:
    Map(QGraphicsScene *scene);
    ~Map();
    bool addTile(std::string name, int x, int y, int z);
    static int getTileSize();
    static bool isEditor();
    void move(int x, int y);
    std::string getTile(int x, int y, int z);
    bool contains(int x, int y, int z);
    void addObject(MapObject *mapObject);
    void addRiver(int length, int startx, int starty, int startz);
    void addRoad(int length, int startx, int starty, int startz);
    void addDungeon(Coords enter, Coords exit, int width, int height);
    void removeObject(MapObject *mapObject);
    void loadMapFromJson(Json::Value config);
    Json::Value saveMapToJson();
    void loadFromJson(Json::Value config);
    Json::Value saveToJson();
    void ensureSize(Player *player);
    void hide();
    Json::Value saveStateToJson();
    void loadStateFromJson(Json::Value config);
    QGraphicsScene *getScene() const;
    void showAll();
    void mapUp();
    void mapDown();
    int getCurrentMap();
    std::set<MapObject*> *getObjects();
    void loadMapFromTmx(Tmx::Map &map);
    int getEntryX()
    {
        return entryx;
    }
    int getEntryY()
    {
        return entryy;
    }
    int getEntryZ()
    {
        return entryz;
    }
private:
    std::set<MapObject*> mapObjects;
    void randomDir(int *tab, int rule);
    std::map<Coords, Tile *> tiles;
    QGraphicsScene *scene;
    int currentMap = 0;
    std::map<int, std::string> defaultTiles;
    int entryx, entryz, entryy;
};

class MapObject : public AnimatedObject
{
public:
    MapObject();
    MapObject(int x, int y, int z, int v);
    ~MapObject();
    std::string className;
    int posx, posy, posz;
    virtual void moveTo(int x, int y, int z, bool silent = false);
    int getPosX() const;
    int getPosY() const;
    int getPosZ() const;
    void removeFromGame();
    virtual void onEnter() = 0;
    virtual void onMove() = 0;
    void move(int x, int y);
    virtual void loadFromJson(Json::Value config) = 0;
    virtual void loadFromProps(Tmx::PropertySet) {}
    virtual Json::Value saveToJson() = 0;
    virtual bool canSave() = 0;
    virtual void setMap(Map *map);
    Map *getMap();
    void setVisible(bool vis);
protected:
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    void setAnimation(std::string path);
    Map *map = 0;
    QGraphicsItemAnimation *dynamicAnimation = 0;
    QTimeLine *timer = 0;
    QGraphicsSimpleTextItem statsView;
};

class PlayerAnimation : public QGraphicsItemAnimation
{
public:
    explicit PlayerAnimation(QObject *parent = 0);
protected:
    virtual void    afterAnimationStep(qreal step);
};

#endif // MAP_H
