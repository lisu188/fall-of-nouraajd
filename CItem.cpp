#include "CItem.h"
#include "CGameScene.h"
#include "Stats.h"
#include <QDebug>
#include <QDrag>
#include <QJsonObject>
#include <fstream>
#include "CInteraction.h"
#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "CMap.h"
#include "CInteraction.h"
#include "CObjectHandler.h"
#include "CPlayerView.h"
#include "CGameView.h"
#include "CGuiHandler.h"

CItem::CItem()  {
	this->setZValue ( 2 );
}

CItem::CItem ( const CItem & )  { }

void CItem::onEnter(CCreature * creature) {
	this->getMap()->removeObject ( this );
    creature->addItem ( this );
}

bool CItem::isSingleUse() {
	return singleUse;
}

void CItem::setSingleUse ( bool singleUse ) {
	this->singleUse = singleUse;
}

void CItem::onEquip ( CCreature *creature ) {
	creature->addBonus ( bonus );
	qDebug() << creature->getTypeName()  << "equipped" << getTypeName()
	         << "\n";
}

void CItem::onUnequip ( CCreature *creature ) {
	creature->removeBonus ( bonus );
	qDebug() << creature->getTypeName()  << "unequipped" << getTypeName()
	         << "\n";
}

void CItem::onUse ( CCreature *creature ) {
	CItemSlot *parent = dynamic_cast<CItemSlot *> ( this->parentItem() );
	if ( !parent ) {
		return;
	}
	int slot = parent->getNumber();
	if ( slot==-1 ) {
		return;
	}
	creature->setItem ( slot, this );
}

void CItem::mousePressEvent ( QGraphicsSceneMouseEvent *event ) {
	if ( singleUse && this->getMap()->getScene()->getPlayer() ) {
		onUse ( this->getMap()->getScene()->getPlayer() );
		this->getMap()->getScene()->getPlayer()->removeFromInventory ( this );
		delete this;
		return;
	}
	QDrag *drag = new QDrag ( this );
	drag->setMimeData ( new CObjectData ( this ) );
	drag->setPixmap ( this->pixmap() );
	drag->exec();
	if ( event->isAccepted() ) {
		return;
	}
	if ( this->getMap()->getScene()->getPlayer() && !this->getMap()->getScene()->getPlayer()->hasItem ( this ) ) {
		return;
	}
	QGraphicsObject *parent = this->parentObject();
	if ( parent ) {
		parent->setAcceptDrops ( false );
	}
	drag = new QDrag ( this );
	drag->setMimeData ( new CObjectData ( this ) );
	drag->setPixmap ( this->pixmap() );
	drag->exec();
	if ( parent ) {
		parent->setAcceptDrops ( true );
	}
}

int CItem::getPower() const {
	return power;
}

void CItem::setPower ( int value ) {
	power = value;
}

CArmor::CArmor() {

}

CArmor::CArmor ( const CArmor & ) {

}

CInteraction *CItem::getInteraction() {
	return interaction;
}

CBelt::CBelt() {

}

CBelt::CBelt ( const CBelt & ) {

}

CBoots::CBoots() {

}

CBoots::CBoots ( const CBoots & ) {

}

CGloves::CGloves() {

}

CGloves::CGloves ( const CGloves & ) {

}

CHelmet::CHelmet() {

}

CHelmet::CHelmet ( const CHelmet & ) {

}

CSmallWeapon::CSmallWeapon() {

}

CSmallWeapon::CSmallWeapon ( const CSmallWeapon & ) {

}

CWeapon::CWeapon() : CItem() {

}

CWeapon::CWeapon ( const CWeapon & ) {

}

Stats CItem::getBonus() {
	return bonus;
}

void CItem::setBonus ( Stats stats ) {
	this->bonus=stats;
}

QString CItem::getInteractionName() {
	if ( interaction ) {
		return interaction->getTypeName();
	}
	return "";
}

void CItem::setInteractionName ( QString name ) {
	interaction=this->getMap()->getObjectHandler()->createMapObject<CInteraction*> ( name );
	interaction->setManaCost ( 0 );
}

CPotion::CPotion() {

}

CPotion::CPotion ( const CPotion & ) {

}

void CPotion::onUse ( CCreature * ) {

}

CScroll::CScroll() {

}

CScroll::CScroll ( const CScroll & ) {

}

QString CScroll::getText() const {
	return text;
}

void CScroll::setText ( const QString &value ) {
	text = value;
}

void CScroll::onUse ( CCreature * ) {
	getMap()->getGuiHandler()->showMessage ( text );
}
