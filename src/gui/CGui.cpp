#include "CGui.h"

CGui::CGui() {
    SDL_Init(SDL_INIT_VIDEO);
    SDL_CreateWindowAndRenderer(1920, 1080, SDL_WINDOW_FULLSCREEN | SDL_WINDOW_OPENGL, &window, &renderer);
}

CGui::~CGui() {
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
}
