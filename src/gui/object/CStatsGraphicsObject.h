#pragma once

#include "CGameGraphicsObject.h"

class CStatsGraphicsObject : public CGameGraphicsObject {
V_META(CStatsGraphicsObject, CGameGraphicsObject, vstd::meta::empty())
    std::function<std::shared_ptr<CPlayer>()> _player;
public:
    CStatsGraphicsObject(std::function<std::shared_ptr<CPlayer>()> _player);

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime, std::string data) override;

};