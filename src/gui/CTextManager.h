#pragma once

#include "object/CGameObject.h"
#include "gui/CAnimation.h"
#include "gui/CGui.h"


class CTextManager : public CGameObject {
V_META(CTextManager, CGameObject, vstd::meta::empty())
    std::unordered_map<std::pair<std::string, int>, SDL_Texture *> _textures;
public:
    CTextManager(std::shared_ptr<CGui> _gui = nullptr);

    ~CTextManager();

    void drawText(std::string text, int x, int y, int h);

    void drawTextCentered(std::string text, int x, int y, int w, int h);
private:
    SDL_Texture *getTexture(std::string text, int width = -1);

    SDL_Texture *loadTexture(std::string text, int width = -1);

    std::weak_ptr<CGui> _gui;

    struct _TTF_Font *font;
};
