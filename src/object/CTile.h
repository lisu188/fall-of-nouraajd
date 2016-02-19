#pragma once

#include "core/CGlobal.h"
#include "CMapObject.h"

class CGame;

class CCreature;

class CTile : public CGameObject {

V_META(CTile, CGameObject,
       V_PROPERTY(CTile, bool, canStep, canStep, setCanStep),
       V_PROPERTY(CTile, int, posx, getPosx, setPosx),
       V_PROPERTY(CTile, int, posy, getPosy, setPosy),
       V_PROPERTY(CTile, int, posz, getPosz, setPosz),
       V_PROPERTY(CTile, std::string, tileType, getTileType, setTileType)
)

public:
    CTile();

    virtual ~CTile();

    virtual void onStep(std::shared_ptr<CCreature>);

    void move(int x, int y, int z);

    void moveTo(int x, int y, int z);

    Coords getCoords();

    bool canStep() const;

    void setCanStep(bool canStep);

    int getPosx() const;

    void setPosx(int value);

    int getPosy() const;

    void setPosy(int value);

    int getPosz() const;

    void setPosz(int value);

    const std::string &getTileType() const;

    void setTileType(const std::string &tileType);

private:
    std::string tileType;
    bool step = false;
    int posx = 0, posy = 0, posz = 0;

    void setXYZ(int x, int y, int z);
};


