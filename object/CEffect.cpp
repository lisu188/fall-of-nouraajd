#include "CEffect.h"
#include "CCreature.h"

CEffect::CEffect() {

}

CEffect::CEffect ( const CEffect & ) {

}

CEffect::~CEffect() {

}

int CEffect::getTimeLeft() {
	return timeLeft;
}

int CEffect::getTimeTotal() {
	return timeTotal;
}

CCreature *CEffect::getCaster() {
	return caster;
}

CCreature *CEffect::getVictim() {
	return victim;
}

bool CEffect::apply ( CCreature *creature ) {
	if ( bonus )
		if ( timeTotal == timeLeft ) {
			creature->addBonus ( *bonus );
		}
	timeLeft--;
	if ( timeLeft == 0 ) {
		if ( bonus ) {
			creature->removeBonus ( *bonus );
		}
		return false;
	}
	return onEffect();
}

Stats *CEffect::getBonus() {
	return bonus;
}

void CEffect::setBonus ( Stats *value ) {
	bonus = value;
}

int CEffect::getDuration() {
	return duration;
}

void CEffect::setDuration ( int duration ) {
	this->duration=duration;
	timeLeft = timeTotal =duration;
}

bool CEffect::onEffect() {
	return false;
}

bool CEffect::isBuff() const {
	return buff;
}

void CEffect::setBuff ( bool value ) {
	buff = value;
}

void CEffect::setCaster ( CCreature *value ) {
	caster = value;
}

void CEffect::setVictim ( CCreature *value ) {
	victim = value;
}

