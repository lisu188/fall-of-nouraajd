#include "CBuilding.h"
#include <QDebug>
#include "CGameScene.h"
#include "CPlayerView.h"

CBuilding::CBuilding() {
	this->setZValue ( 1 );
}

CBuilding::CBuilding ( const CBuilding & ) {

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
