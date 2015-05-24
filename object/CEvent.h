#pragma once
#include "CMapObject.h"

class CEvent : public CMapObject,public Visitable {
    Q_OBJECT
    Q_PROPERTY ( bool enabled READ isEnabled WRITE setEnabled USER true )
public:
    CEvent();

    bool isEnabled();
    void setEnabled ( bool enabled );

    virtual void onEnter ( std::shared_ptr<CGameEvent> ) override ;
    virtual void onLeave ( std::shared_ptr<CGameEvent> ) override ;
private:
    bool enabled = true;
};
