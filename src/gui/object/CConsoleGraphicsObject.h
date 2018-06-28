#pragma once

#include "CGameGraphicsObject.h"

class CConsoleGraphicsObject : public CGameGraphicsObject {
V_META(CConsoleGraphicsObject, CGameGraphicsObject,
       V_PROPERTY(CConsoleGraphicsObject, std::string, consoleState, getConsoleState, setConsoleState),
       V_PROPERTY(CConsoleGraphicsObject, std::list<std::string>, consoleHistory, getConsoleHistory, setConsoleHistory))
//TODO: make this properties
    int height = 30;
    int width = 200;

public:
    CConsoleGraphicsObject();

    void render(std::shared_ptr<CGui> gui, SDL_Rect *pos, int frameTime) override;

    std::string getConsoleState();

    void setConsoleState(std::string consoleState);

    std::list<std::string> getConsoleHistory();

    void setConsoleHistory(std::list<std::string> consoleHistory);

private:
    bool inProgress = false;
    std::string consoleState = "";
    //TODO: persist order when saving
    std::vector<std::string> consoleHistory = {""};
    int historyIndex = 0;

    void stopInput();

    void startInput();

    void clearConsole();

    void decrementHistoryIndex();

    void incrementHistoryIndex();
};