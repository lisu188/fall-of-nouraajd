
#include "CTextureCache.h"

SDL_Texture *CTextureCache::getTexture(std::string path) {
    auto anim = _textures.find(path);
    if (anim == _textures.end()) {
        _textures[path] = this->loadTexture(path);
        return getTexture(path);
    }
    return _textures[path];
}

SDL_Texture *CTextureCache::loadTexture(std::string path) {
    return IMG_LoadTexture(_gui.lock()->getRenderer(), path.c_str());
}

CTextureCache::CTextureCache(std::shared_ptr<CGui> _gui) : _gui(_gui) {}

CTextureCache::~CTextureCache() {
    for (auto texture:_textures) {
        SDL_DestroyTexture(texture.second);
    }
    _textures.clear();
}

CTextureCache::CTextureCache() {

}
