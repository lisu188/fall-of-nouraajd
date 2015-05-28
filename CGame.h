#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "gui/CGui.h"
#include "handler/CHandler.h"

class CGameView;
class CPlayer;
class CMap;
class CGameObject;

class CGame : private QGraphicsScene,public std::enable_shared_from_this<CGame> {
    Q_OBJECT
    friend class CGameView;
public:
    CGame ( std::shared_ptr<CGameView> view );
    ~CGame();
    void changeMap ( QString file );
    std::shared_ptr<CMap> getMap() const;
    void setMap ( std::shared_ptr<CMap> map );
    std::shared_ptr<CGameView> getView();
    void removeObject ( std::shared_ptr<CGameObject> object );
    void addObject ( std::shared_ptr<CGameObject> object );
    std::shared_ptr<CGuiHandler> getGuiHandler();
    std::shared_ptr<CScriptHandler> getScriptHandler();
    std::shared_ptr<CObjectHandler> getObjectHandler();
    std::shared_ptr<CGame> ptr();
protected:
    virtual void keyPressEvent ( QKeyEvent *event );
private:
    Lazy<CGuiHandler,std::shared_ptr<CGame>> guiHandler;
    Lazy<CScriptHandler> scriptHandler;
    Lazy<CScriptWindow,std::shared_ptr<CGame>> scriptWindow;
    Lazy<CObjectHandler> objectHandler;
    std::shared_ptr<CMap> map;
    std::weak_ptr<CGameView> view;
};

