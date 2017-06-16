#pragma once

#include "CGameGraphicsObject.h"

//TODO: write numeric values on bars
class CStatsGraphicsObject : public CGameGraphicsObject {
V_META(CStatsGraphicsObject, CGameGraphicsObject, vstd::meta::empty())
//TODO: get rid of this ugly callback!
    std::function<std::shared_ptr<CPlayer>()> _player;
public:
    CStatsGraphicsObject();

    CStatsGraphicsObject(std::function<std::shared_ptr<CPlayer>()> _player);

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime, std::string data) override;

};