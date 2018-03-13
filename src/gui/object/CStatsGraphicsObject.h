#pragma once

#include "CGameGraphicsObject.h"

//TODO: write numeric values on bars
class CStatsGraphicsObject : public CGameGraphicsObject {
V_META(CStatsGraphicsObject, CGameGraphicsObject, vstd::meta::empty())
    int height = 30;
    int width = 200;
public:
    CStatsGraphicsObject();

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) override;

private:
    void drawBar(std::shared_ptr<CGui> gui, int ratio, int index, SDL_Rect *pos, Uint8 r, Uint8 g, Uint8 b,
                 Uint8 a);

    void drawValues(std::shared_ptr<CGui> gui, int left, int right, int index, SDL_Rect *pos);
};