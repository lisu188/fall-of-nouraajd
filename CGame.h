#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "gui/CGui.h"
#include "handler/CHandler.h"

class CGameView;
class CPlayer;
class CMap;
class CGameObject;
class CGame : private QGraphicsScene {
    Q_OBJECT
    friend class CGameView;
public:
    CGame ();
    void changeMap ( QString file );
    std::shared_ptr<CMap> getMap() const;
    void setMap ( std::shared_ptr<CMap> map );
    CGameView *getView();
    void removeObject ( CGameObject *object );
    void addObject ( CGameObject *object );
    CGuiHandler *getGuiHandler();
    CScriptHandler *getScriptHandler();
    CObjectHandler *getObjectHandler();
protected:
    virtual void keyPressEvent ( QKeyEvent *event );
private:
    Lazy<CGuiHandler,CGame*> guiHandler;
    Lazy<CScriptHandler> scriptHandler;
    Lazy<CScriptWindow,std::shared_ptr<CGame>> scriptWindow;
    Lazy<CObjectHandler> objectHandler;
    std::shared_ptr<CMap> map;
};

