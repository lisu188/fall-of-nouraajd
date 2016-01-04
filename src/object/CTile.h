#pragma once

#include "core/CGlobal.h"
#include "CMapObject.h"

class CGame;

class CCreature;

class CTile : public CGameObject {

    Q_PROPERTY ( bool canStep
                 READ
                 canStep
                 WRITE
                 setCanStep
                 USER
                 true )
    Q_PROPERTY ( int posx
                 READ
                 getPosx
                 WRITE
                 setPosx
                 USER
                 true )
    Q_PROPERTY ( int posy
                 READ
                 getPosy
                 WRITE
                 setPosy
                 USER
                 true )
    Q_PROPERTY ( int posz
                 READ
                 getPosz
                 WRITE
                 setPosz
                 USER
                 true )
public:
    CTile();

    virtual ~CTile();

    virtual void onStep ( std::shared_ptr<CCreature> );

    void move ( int x, int y, int z );

    void moveTo ( int x, int y, int z );

    Coords getCoords();

    bool canStep() const;

    void setCanStep ( bool canStep );

    int getPosx() const;

    void setPosx ( int value );

    int getPosy() const;

    void setPosy ( int value );

    int getPosz() const;

    void setPosz ( int value );

private:
    bool step = false;
    int posx = 0, posy = 0, posz = 0;

    void setXYZ ( int x, int y, int z );
};

GAME_PROPERTY ( CTile )
