#include "CBuilding.h"
#include <QDebug>
#include "CGameScene.h"
#include "CPlayerView.h"
#include "CConfigurationProvider.h"
#include "CScriptEngine.h"

CBuilding::CBuilding() {}

CBuilding::CBuilding ( const CBuilding & ) {}

void CBuilding::onEnter() {

}

void CBuilding::onMove() {

}

void CBuilding::onCreate() {

}

void CBuilding::onDestroy() {

}

void CBuilding::loadFromJson ( QString name ) {
	this->typeName = name;
	QJsonObject config =
	    CConfigurationProvider::getConfig ( "config/object.json" ).toObject() [name].toObject();
	this->setAnimation ( config["animation"].toString() );
}

bool CBuilding::isEnabled() { return enabled; }

void CBuilding::setEnabled ( bool enabled ) { this->enabled = enabled; }

