#pragma once

class CGameObject;
class CMap;

class CClickAction {
public:
    virtual void onClickAction ( CGameObject *object ) =0;
};

class CMouseHandler  {
public:
    CMouseHandler ();
    void handleClick ( CGameObject *object );
private:
    CClickAction *getClickAction ( CGameObject *object );
};
