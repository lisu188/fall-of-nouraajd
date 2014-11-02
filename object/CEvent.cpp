#include "CEvent.h"
#include "CMap.h"
#include <boost/ref.hpp>

CEvent::CEvent() {

}

CEvent::CEvent ( const CEvent & ) {

}

bool CEvent::isEnabled() {
	return enabled;
}

void CEvent::setEnabled ( bool enabled ) {
	this->enabled = enabled;
}

QString CEvent::getEventClass() {
	return eventClass;
}

void CEvent::setEventClass ( const QString &value ) {
	this->eventClass=value;
	CEvent* event=this;
	getMap()->getScriptHandler()->callFunction ( "game.switchClass", boost::ref ( event ),getMap()->getScriptHandler()->getObject ( getMap()->getMapName()+"."+value )  );
}

void CEvent::onEnter ( CGameEvent * ) {

}

void CEvent::onLeave ( CGameEvent * ) {

}

