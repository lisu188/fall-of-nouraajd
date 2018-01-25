#include "CTrigger.h"

CTrigger::CTrigger() {
}

void CTrigger::trigger(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>) {

}

std::string CTrigger::getObject() {
    return object;
}

void CTrigger::setObject(std::string object) {
    CTrigger::object = object;
}

std::string CTrigger::getEvent() {
    return event;
}

void CTrigger::setEvent(std::string event) {
    CTrigger::event = event;
}
