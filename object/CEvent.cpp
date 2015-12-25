#include "CEvent.h"
#include "core/CMap.h"

CEvent::CEvent() {

}

bool CEvent::isEnabled() {
    return enabled;
}

void CEvent::setEnabled ( bool enabled ) {
    this->enabled = enabled;
}

void CEvent::onEnter ( std::shared_ptr<CGameEvent> ) {

}

void CEvent::onLeave ( std::shared_ptr<CGameEvent> ) {

}

