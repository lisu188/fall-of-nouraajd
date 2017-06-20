#pragma once

#include "CGameGraphicsObject.h"

//TODO: write numeric values on bars
class CStatsGraphicsObject : public CGameGraphicsObject {
V_META(CStatsGraphicsObject, CGameGraphicsObject, vstd::meta::empty())
//TODO: get rid of this ugly callback!
    std::function<std::shared_ptr<CPlayer>()> _player;
    int height = 30;
    int width = 200;
public:
    CStatsGraphicsObject();

    CStatsGraphicsObject(std::function<std::shared_ptr<CPlayer>()> _player);

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) override;

private:
    void drawBar(std::shared_ptr<CGui> gui, int ratio, int index, SDL_Rect *pos, Uint8 r, Uint8 g, Uint8 b,
                 Uint8 a);
};