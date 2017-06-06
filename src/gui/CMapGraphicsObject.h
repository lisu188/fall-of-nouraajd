#pragma once

#include "gui/CGameGraphicsObject.h"

class CMapGraphicsObject : public CGameGraphicsObject {
V_META(CMapGraphicsObject, CGameGraphicsObject, vstd::meta::empty())

    std::function<std::shared_ptr<CMap>()> _map;
public:
    CMapGraphicsObject(std::function<std::shared_ptr<CMap>()> _map);

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime, std::string data) override;

};

