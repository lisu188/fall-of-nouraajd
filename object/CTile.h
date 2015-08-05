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
    Q_PROPERTY ( int posx READ getPosx WRITE setPosx USER true )
    Q_PROPERTY ( int posy READ getPosy WRITE setPosy USER true )
    Q_PROPERTY ( int posz READ getPosz WRITE setPosz USER true )
    Q_PROPERTY ( bool saved READ isSaved WRITE setSaved USER true )
public:
    CTile();
    virtual ~CTile();
    virtual void onStep ( CCreature * );
    void move ( int x, int y, int z ) ;
    void moveTo ( int x,int y,int z );
    Coords getCoords();
    bool canStep() const;
    void setCanStep ( bool canStep );

    int getPosx() const;
    void setPosx ( int value );
    int getPosy() const;
    void setPosy ( int value );
    int getPosz() const;
    void setPosz ( int value );

    bool isSaved() const;
    void setSaved ( bool value );

private:
    bool step=false;
    bool saved=true;
    int posx=0,posy=0,posz=0;
    void setXYZ ( int x, int y, int z );
};
GAME_PROPERTY ( CTile )
