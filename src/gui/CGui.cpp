#include "CGui.h"


CGui::CGui() {
    SDL_Init(SDL_INIT_VIDEO);
    SDL_CreateWindowAndRenderer(width, height, SDL_WINDOW_OPENGL, &window, &renderer);
    //TODO: check render flags
}

CGui::~CGui() {
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
}

void CGui::render(int frameTime) {
    SDL_SetRenderDrawColor(renderer, BLACK);
    SDL_RenderClear(renderer);
    for (std::shared_ptr<CGameGraphicsObject> object:gui_stack) {
        SDL_Rect physical;
        physical.x = 0;
        physical.y = 0;
        physical.h = height;
        physical.w = width;
        object->render(this->ptr<CGui>(), &physical, frameTime);
    }
    SDL_RenderPresent(renderer);
}

bool CGui::event(SDL_Event *event) {
    for (std::shared_ptr<CGameGraphicsObject> object:gui_stack | boost::adaptors::reversed) {
        if (object->event(this->ptr<CGui>(), event)) {
            return true;
        }
    }
    return false;
}

void CGui::addObject(std::shared_ptr<CGameGraphicsObject> object) {
    gui_stack.push_back(object);
}

void CGui::removeObject(std::shared_ptr<CGameGraphicsObject> object) {
    gui_stack.erase(
            std::remove_if(gui_stack.begin(), gui_stack.end(), [object](std::shared_ptr<CGameGraphicsObject> ob) {
                return ob.get() == object.get();
            }), gui_stack.end());
}

SDL_Renderer *CGui::getRenderer() const {
    return renderer;
}

std::shared_ptr<CTextureCache> CGui::getTextureCache() {
    return _textureCache.get([this]() {
        return std::make_shared<CTextureCache>(this->ptr<CGui>());
    });
}

int CGui::getWidth() {
    return width;
}

void CGui::setWidth(int width) {
    CGui::width = width;
}

int CGui::getHeight() {
    return height;
}

void CGui::setHeight(int height) {
    CGui::height = height;
}

int CGui::getTileSize() {
    return tileSize;
}

void CGui::setTileSize(int tileSize) {
    CGui::tileSize = tileSize;
}

int CGui::getTileCountX() {
    return width / tileSize;
}

int CGui::getTileCountY() {
    return height / tileSize;
}

CGui::CGui(std::shared_ptr<CGame> game) : CGui() {
    _game = game;
}

std::shared_ptr<CGame> CGui::getGame() {
    return _game.lock();
}
