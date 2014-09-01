#include "CBuilding.h"
#include <QDebug>
#include <src/gamescene.h>
#include <src/playerstatsview.h>
#include <src/monster.h>
#include "CConfigurationProvider.h"
#include <src/scriptmanager.h>

CBuilding::CBuilding() : MapObject ( 0, 0, 0, 2 ) {}

CBuilding::CBuilding ( const CBuilding & ) {}

void CBuilding::onEnter() {

}

void CBuilding::onMove() {

}

void CBuilding::onCreate() {

}

void CBuilding::onDestroy() {

}

void CBuilding::loadFromJson ( std::string name ) {
	this->typeName = name;
	Json::Value config =
	    ( *CConfigurationProvider::getConfig ( "config/object.json" ) ) [name];
	this->setAnimation ( config.get ( "animation", "" ).asString() );
}

bool CBuilding::isEnabled() { return enabled; }

void CBuilding::setEnabled ( bool enabled ) { this->enabled = enabled; }

