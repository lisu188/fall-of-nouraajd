#pragma once

#include "CGameGraphicsObject.h"

class CCreature;

//TODO: move from here
class CStatsGraphicsUtil {
public:
    static void
    drawStats(std::shared_ptr<CGui> gui, std::shared_ptr<CCreature> creature, int x, int y, int h, int w,
              bool showNumeric,
              bool showExp);

private:
    static void drawBar(std::shared_ptr<CGui> gui, int ratio, int index, Uint8 r, Uint8 g, Uint8 b,
                        Uint8 a, int x, int y, int h, int w);

    static void drawValues(std::shared_ptr<CGui> gui, int left, int right, int index, int x, int y, int h, int w);
};

class CStatsGraphicsObject : public CGameGraphicsObject {
V_META(CStatsGraphicsObject, CGameGraphicsObject, vstd::meta::empty())
    int height = 100;
    int width = 200;
public:
    CStatsGraphicsObject();

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) override;
};