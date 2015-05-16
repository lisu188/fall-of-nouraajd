#pragma once

#include "Util.h"
#include "CGameObject.h"

class CGameEvent;
class CMap;
class CCreature;

class CMapObject : public CGameObject ,public Creatable,public Turnable {
    friend class CObjectHandler;
    Q_OBJECT
public:
    CMapObject();
    virtual ~CMapObject();
    int posx=0, posy=0, posz=0;
    int getPosX() const;
    int getPosY() const;
    int getPosZ() const;

    virtual void onTurn ( CGameEvent * ) override;

    virtual void onCreate ( CGameEvent * ) override;
    virtual void onDestroy ( CGameEvent * ) override;

    Coords getCoords();
    void setCoords ( Coords coords );

    virtual void move ( int x, int y , int z );
    void move ( Coords coords );
    void moveTo ( int x, int y, int z );
    void moveTo ( Coords coords );

private:
    void onMapChanged();
};


