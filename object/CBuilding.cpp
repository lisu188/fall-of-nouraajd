#include "CBuilding.h"

CBuilding::CBuilding() {
    this->setZValue(1);
}

CBuilding::~CBuilding() {

}

bool CBuilding::isEnabled() {
    return enabled;
}

void CBuilding::setEnabled(bool enabled) {
    this->enabled = enabled;
}

void CBuilding::onEnter(std::shared_ptr<CGameEvent>) {
}

void CBuilding::onLeave(std::shared_ptr<CGameEvent>) {
}
