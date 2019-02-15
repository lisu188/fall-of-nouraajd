#pragma once


#include "gui/object/CGameGraphicsObject.h"

class CGui;

class CAnimation : public CGameGraphicsObject {
V_META(CAnimation, CGameGraphicsObject, vstd::meta::empty())
};

class CStaticAnimation : public CAnimation {
V_META(CStaticAnimation, CAnimation, vstd::meta::empty())

    std::string raw_path;
public:
    CStaticAnimation();

    CStaticAnimation(std::string path);

    void render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) override;


};

class CDynamicAnimation : public CAnimation {
V_META(CDynamicAnimation, CAnimation, vstd::meta::empty())
public:
    CDynamicAnimation();

    CDynamicAnimation(std::string path);

    void render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) override;

private:
    static int get_next();

    static int get_ttl();


    std::vector<std::string> paths;
    std::vector<int> times;

    vstd::cache<std::string, int, get_next, get_ttl> _offsets;
    vstd::cache2<std::string, std::vector<int>, get_ttl> _tables;

    int size = 0;
};