#pragma once


#include "gui/CGameGraphicsObject.h"

class CGui;

class CAnimation : public CGameGraphicsObject {
V_META(CAnimation, CGameGraphicsObject, vstd::meta::empty())
};

class CStaticAnimation : public CAnimation {
V_META(CStaticAnimation, CAnimation, vstd::meta::empty())
    SDL_Texture *texture = nullptr;
    std::string raw_path;
public:
    CStaticAnimation(std::string path);

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) override;

    ~CStaticAnimation();
};

class CDynamicAnimation : public CAnimation {
V_META(CDynamicAnimation, CAnimation, vstd::meta::empty())
public:
    CDynamicAnimation(std::string path);

    ~CDynamicAnimation();

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) override;

private:
    std::vector<std::string> paths;
    std::vector<int> times;
    std::vector<SDL_Texture *> textures;

    int getCurrentAnimFrame(int frameTime);

    int size = 0;
    int totalAnimTime = 0;
};