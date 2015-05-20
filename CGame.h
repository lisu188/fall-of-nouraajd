#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "handler/CHandler.h"

class CGameView;
class CPlayer;
class CMap;
class CGameObject;
class CGame : private QGraphicsScene {
    Q_OBJECT
    friend class CGameView;
public:
    CGame ( QObject *parent );
    virtual ~CGame();
    void startGame ( QString file ,QString player );
    void changeMap ( QString file );
    CMap *getMap() const;
    CGameView *getView();
    void removeObject ( CGameObject *object );
    void addObject ( CGameObject *object );
    CGuiHandler *getGuiHandler();
    CConfigHandler *getConfigHandler();
    CScriptHandler *getScriptHandler();
protected:
    virtual void keyPressEvent ( QKeyEvent *event );
private:
    Lazy<CGuiHandler,CGame*> guiHandler;
    Lazy<CScriptHandler> scriptHandler;
    Lazy<CConfigHandler,std::set<QString>> configHandler;
    CMap *map=0;
};

