#include "CItem.h"
#include "CGameScene.h"
#include"CItemSlot.h"
#include <src/Stats.h>
#include <QDebug>
#include <QDrag>
#include <lib/json/json.h>
#include <src/CItem.h>
#include <fstream>
#include "CInteraction.h"
#include <src/CItem.h>
#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "CMap.h"
#include "CInteraction.h"

CItem::CItem() : CMapObject ( 0, 0, 0, 2 ) {}

CItem::CItem ( const CItem &item ) : CItem() { this->loadFromJson ( item.name ); }

void CItem::onEnter() {
	this->getMap()->removeObject ( this );
	this->getMap()->getScene()->getPlayer()->addItem ( this );
}

void CItem::onMove() {}

bool CItem::isSingleUse() { return singleUse; }

void CItem::setSingleUse ( bool singleUse ) { this->singleUse = singleUse; }

void CItem::onEquip ( CCreature *creature ) {
	creature->getStats()->addBonus ( bonus );
	qDebug() << creature->typeName.c_str() << "equipped" << typeName.c_str()
	         << "\n";
}

void CItem::onUnequip ( CCreature *creature ) {
	creature->getStats()->removeBonus ( bonus );
	qDebug() << creature->typeName.c_str() << "unequipped" << typeName.c_str()
	         << "\n";
}

void CItem::onUse ( CCreature *creature ) {
	CItemSlot *parent = ( CItemSlot * ) this->parentItem();
	if ( !parent ) {
		qDebug() << "Parentless item dropped";
		return;
	}
	int slot = parent->getNumber();
	creature->setItem ( slot, this );
}

void CItem::mousePressEvent ( QGraphicsSceneMouseEvent *event ) {
	if ( singleUse && this->getMap()->getScene()->getPlayer() ) {
		this->getMap()->getScene()->getPlayer()->removeFromInventory ( this );
		onUse ( this->getMap()->getScene()->getPlayer() );
		delete this;
		return;
	}
	CMapObject::mousePressEvent ( event );
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
	CAnimatedObject::mousePressEvent ( event );
	if ( parent ) {
		parent->setAcceptDrops ( true );
	}
}

void CItem::loadFromJson ( std::string name ) {
	this->typeName = name;
	Json::Value config =
	    ( *CConfigurationProvider::getConfig ( "config/object.json" ) ) [typeName];
	bonus.loadFromJson ( config["bonus"] );
	interaction =
	    this->getMap()->createMapObject<CInteraction*>  ( config.get ( "interaction", "" ).asString() );
	setAnimation ( config.get ( "animation", "" ).asCString() );
	power = config.get ( "power", 1 ).asInt();
	singleUse = config.get ( "singleUse", false ).asBool();
	tooltip = config.get ( "tooltip", "" ).asString();
	slot = config.get ( "slot", 0 ).asInt();
	if ( tooltip.compare ( "" ) == 0 ) {
		tooltip = typeName;
	}
}
int CItem::getPower() const { return power; }

void CItem::setPower ( int value ) { power = value; }

CArmor::CArmor() {}

CArmor::CArmor ( const CArmor &armor ) {}

CInteraction *CArmor::getInteraction() { return interaction; }

CBelt::CBelt() {}

CBelt::CBelt ( const CBelt &belt ) {}

CBoots::CBoots() {}

CBoots::CBoots ( const CBoots &boots ) {}

CGloves::CGloves() {}

CGloves::CGloves ( const CGloves &gloves ) {}

CHelmet::CHelmet() {}

CHelmet::CHelmet ( const CHelmet &helmet ) {}

CSmallWeapon::CSmallWeapon() {}

CSmallWeapon::CSmallWeapon ( const CSmallWeapon &weapon ) {}

CWeapon::CWeapon() : CItem() {}

CWeapon::CWeapon ( const CWeapon &weapon ) {}

CInteraction *CWeapon::getInteraction() { return interaction; }

Stats *CWeapon::getStats() { return &bonus; }

#include "CItem.h"
#include <QDebug>
#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "CGameScene.h"

CPotion::CPotion() {}

CPotion::CPotion ( const CPotion & ) {}

void CPotion::onUse ( CCreature *creature ) {
	qDebug() << creature->typeName.c_str() << "used" << typeName.c_str();
	effect ( creature, power );
}

void CPotion::loadFromJson ( std::string name ) {
	CItem::loadFromJson ( name );
	if ( ( std::string ( typeName ).find ( "LifePotion" ) != std::string::npos ) ) {
		effect = &LifeEffect;
	} else if ( std::string ( typeName ).find ( "ManaPotion" ) != std::string::npos ) {
		effect = &ManaEffect;
	}
}

void LifeEffect ( CCreature *creature, int power ) {
	creature->healProc ( power * 20 );
}

void ManaEffect ( CCreature *creature, int power ) {
	creature->addManaProc ( power * 20 );
}
