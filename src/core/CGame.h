#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "handler/CHandler.h"
#include "core/CPlugin.h"

class CGameView;

class CPlayer;

class CMap;

class CGameObject;

class CGame : public CGameObject {
V_META(CGame, CGameObject, vstd::meta::empty())
public:
    CGame();

    ~CGame();

    void changeMap(std::string file);

    std::shared_ptr<CMap> getMap() const;

    void setMap(std::shared_ptr<CMap> map);

    std::shared_ptr<CGuiHandler> getGuiHandler();

    std::shared_ptr<CScriptHandler> getScriptHandler();

    std::shared_ptr<CObjectHandler> getObjectHandler();

    void load_plugin(std::function<std::shared_ptr<CPlugin>()> plugin);

    template<typename T>
    std::shared_ptr<T> createObject(std::string name) {
        return getObjectHandler()->createObject<T>(getMap(), name);
    }

protected:
    virtual void keyPressEvent(void *event); //TODO: implement

private:
    vstd::lazy<CGuiHandler, std::shared_ptr<CGame>> guiHandler;
    vstd::lazy<CScriptHandler> scriptHandler;
//TODO:    vstd::lazy<CScriptWindow, std::shared_ptr<CGame>> scriptWindow;
    vstd::lazy<CObjectHandler> objectHandler;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CGui> _gui;
public:
    std::shared_ptr<CGui> getGui() const;

    void setGui(std::shared_ptr<CGui> _gui);
};

