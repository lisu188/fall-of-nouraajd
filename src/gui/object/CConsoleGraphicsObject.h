#pragma once

#include "CGameGraphicsObject.h"

//TODO: implement history
class CConsoleGraphicsObject : public CGameGraphicsObject {
V_META(CConsoleGraphicsObject, CGameGraphicsObject,
       V_PROPERTY(CConsoleGraphicsObject, std::string, consoleState, getConsoleState, setConsoleState))
//TODO: make this properties
    int height = 30;
    int width = 200;

public:
    CConsoleGraphicsObject();

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) override;

    std::string getConsoleState();

    void setConsoleState(std::string consoleState);

private:
    bool inProgress = false;
    std::string consoleState = "";

    void stopInput();

    void startInput();
};