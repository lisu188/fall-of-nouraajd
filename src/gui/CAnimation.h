#pragma once


#include "gui/object/CGameGraphicsObject.h"

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

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime, std::string data) override;

    ~CStaticAnimation();
};

class CDynamicAnimation : public CAnimation {
V_META(CDynamicAnimation, CAnimation, vstd::meta::empty())
public:
    CDynamicAnimation(std::string path);

    ~CDynamicAnimation();

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime, std::string object) override;

private:
    static int get_next();

    static int get_ttl();


    std::vector<std::string> paths;
    std::vector<int> times;
    std::vector<SDL_Texture *> textures;

    vstd::cache<std::string, int, get_next, get_ttl> _offsets;

    int getCurrentAnimFrame(int frameTime);

    int size = 0;
    int totalAnimTime = 0;

    double getFrameOffset(std::string object, int frameTime);
};