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
    CGame (  );
    virtual ~CGame();
    void startGame ( QString file ,QString player );
    void changeMap ( QString file );
    CMap *getMap() const;
    CGameView *getView();
    void removeObject ( CGameObject *object );
    void addObject ( CGameObject *object );
    CGuiHandler *getGuiHandler();
    CScriptHandler *getScriptHandler();
    CObjectHandler *getObjectHandler();
protected:
    virtual void keyPressEvent ( QKeyEvent *event );
private:
    void initObjectHandler ( CObjectHandler *handler );
    Lazy<CGuiHandler,CGame*> guiHandler;
    Lazy<CScriptHandler> scriptHandler;
    Lazy<CScriptWindow,CGame*> scriptWindow;
    Lazy<CObjectHandler> objectHandler;
    CMap *map=0;
};
