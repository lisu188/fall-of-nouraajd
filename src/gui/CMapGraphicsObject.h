#pragma once

#include "gui/CGameGraphicsObject.h"

class CMapGraphicsObject : public CGameGraphicsObject {
V_META(CMapGraphicsObject, CGameGraphicsObject, vstd::meta::empty())

    std::weak_ptr<CMap> _map;
public:
    CMapGraphicsObject(std::shared_ptr<CMap> map);

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int i1) override;

    bool event(SDL_Event *event) override;

};

