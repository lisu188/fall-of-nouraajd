#include "CBuilding.h"

CBuilding::CBuilding() {
    this->setZValue ( 1 );
}

CBuilding::~CBuilding() {

}

bool CBuilding::isEnabled() {
    return enabled;
}

void CBuilding::setEnabled ( bool enabled ) {
    this->enabled = enabled;
}

void CBuilding::onEnter ( CGameEvent * ) {
}

void CBuilding::onLeave ( CGameEvent * ) {
}
