#pragma once

#include "gui/object/CGameGraphicsObject.h"

class CMapGraphicsObject : public CGameGraphicsObject {
V_META(CMapGraphicsObject, CGameGraphicsObject, vstd::meta::empty())


public:
    CMapGraphicsObject();

    void render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) override;

};

