#include "CEvent.h"
#include "CMap.h"
#include <boost/ref.hpp>

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

