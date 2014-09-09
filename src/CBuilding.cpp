#include "CBuilding.h"
#include <QDebug>
#include "CGameScene.h"
#include "CPlayerView.h"
#include "CConfigurationProvider.h"
#include "CScriptEngine.h"

CBuilding::CBuilding() {
	this->setZValue ( 1 );
}

CBuilding::CBuilding ( const CBuilding & ) {}

CBuilding::~CBuilding() {}

void CBuilding::onEnter() {

}

void CBuilding::onMove() {

}

void CBuilding::onCreate() {

}

void CBuilding::onDestroy() {

}

bool CBuilding::isEnabled() { return enabled; }

void CBuilding::setEnabled ( bool enabled ) { this->enabled = enabled; }

