#pragma once

#include "CGameObject.h"

class CTrigger : public CGameObject {
V_META(CTrigger, CGameObject,
       V_PROPERTY(CTrigger, std::string, object, getObject, setObject),
       V_PROPERTY(CTrigger, std::string, event, getEvent, setEvent))
public:
    CTrigger();

    virtual void trigger(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>);

private:
    std::string object;
    std::string event;
public:
    std::string getObject();

    void setObject(std::string object);

    std::string getEvent();

    void setEvent(std::string event);


};


