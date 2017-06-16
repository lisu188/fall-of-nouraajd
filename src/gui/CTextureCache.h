#pragma once

#include "object/CGameObject.h"
#include "gui/CAnimation.h"
#include "gui/CGui.h"

//TODO: generify all cache classes

class CTextureCache : public CGameObject {
V_META(CTextureCache, CGameObject, vstd::meta::empty())
    std::unordered_map<std::string, SDL_Texture *> _textures;
public:
    CTextureCache(std::shared_ptr<CGui> _gui);

    CTextureCache();

    ~CTextureCache();


    SDL_Texture *getTexture(std::string path);

private:
    SDL_Texture *loadTexture(std::string path);

    std::weak_ptr<CGui> _gui;
};
