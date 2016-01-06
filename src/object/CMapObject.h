#pragma once

#include "core/CUtil.h"
#include "CGameObject.h"

class CGameEvent;

class CMap;

class CCreature;

class CMapObject : public CGameObject, public Creatable, public Turnable {
    friend class CObjectHandler;

V_META(CMapObject, CGameObject,
       V_PROPERTY(CMapObject, int, posx, getPosX, setPosX),
       V_PROPERTY(CMapObject, int, posy, getPosY, setPosY),
       V_PROPERTY(CMapObject, int, posz, getPosZ, setPosZ)
)

public:
    CMapObject();

    virtual ~CMapObject();

    void setPosX(int posx) {
        this->posx = posx;
    }

    void setPosY(int posy) {
        this->posy = posy;
    }

    void setPosZ(int posz) {
        this->posz = posz;
    }

    int posx = 0, posy = 0, posz = 0;

    int getPosX() const;

    int getPosY() const;

    int getPosZ() const;

    virtual void onTurn(std::shared_ptr<CGameEvent>) override;

    virtual void onCreate(std::shared_ptr<CGameEvent>) override;

    virtual void onDestroy(std::shared_ptr<CGameEvent>) override;

    Coords getCoords();

    void setCoords(Coords coords);

    virtual void move(int x, int y, int z);

    void move(Coords coords);

    void moveTo(int x, int y, int z);

    void moveTo(Coords coords);
};

GAME_PROPERTY (CMapObject)

