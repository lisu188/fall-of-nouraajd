#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "handler/CHandler.h"

class CGameView;

class CPlayer;

class CMap;

class CGameObject;

class CGame : public std::enable_shared_from_this<CGame> {
public:
    CGame();

    ~CGame();

    void changeMap(std::string file);

    std::shared_ptr<CMap> getMap() const;

    void setMap(std::shared_ptr<CMap> map);

//TODO:   std::shared_ptr<CGuiHandler> getGuiHandler();

    std::shared_ptr<CScriptHandler> getScriptHandler();

    std::shared_ptr<CObjectHandler> getObjectHandler();

    std::shared_ptr<CGame> ptr();

protected:
    virtual void keyPressEvent(void *event); //TODO: implement

private:
//TODO:    vstd::lazy<CGuiHandler, std::shared_ptr<CGame>> guiHandler;
    vstd::lazy<CScriptHandler> scriptHandler;
//TODO:    vstd::lazy<CScriptWindow, std::shared_ptr<CGame>> scriptWindow;
    vstd::lazy<CObjectHandler> objectHandler;
    std::shared_ptr<CMap> map;
};

