#include "CItem.h"
#include "CGame.h"
#include "CStats.h"
#include "CMap.h"
#include "object/CObject.h"
#include "handler/CHandler.h"
#include "gui/CGui.h"

CItem::CItem()  {
    this->setZValue ( 2 );
}

CItem::~CItem() {

}

void CItem::onEnter ( CGameEvent *event ) {
    if ( auto visitor=dynamic_cast<CCreature*> ( dynamic_cast<CGameEventCaused*> ( event )->getCause() ) ) {
        this->getMap()->removeObject ( this );
        visitor->addItem ( this );
    }
}

void CItem::onLeave ( CGameEvent * ) {

}

bool CItem::isSingleUse() {
    return singleUse;
}

void CItem::setSingleUse ( bool singleUse ) {
    this->singleUse = singleUse;
}

void CItem::onEquip ( CGameEvent *event ) {
    dynamic_cast<CCreature*> ( dynamic_cast<CGameEventCaused*> ( event )->getCause() )->addBonus ( bonus );
    qDebug() << dynamic_cast<CGameEventCaused*> ( event )->getCause()->getObjectType()  << "equipped" << getObjectType()
             << "\n";
}

void CItem::onUnequip ( CGameEvent *event ) {
    dynamic_cast<CCreature*> ( dynamic_cast<CGameEventCaused*> ( event )->getCause() )->removeBonus ( bonus );
    qDebug() << dynamic_cast<CGameEventCaused*> ( event )->getCause()->getObjectType()  << "unequipped" << getObjectType()
             << "\n";
}

void CItem::onUse ( CGameEvent * event ) {
    CItemSlot *parent = dynamic_cast<CItemSlot *> ( this->parentItem() );
    if ( !parent ) {
        return;
    }
    int slot = parent->getNumber();
    if ( slot==-1 ) {
        return;
    }
    dynamic_cast<CCreature*> ( dynamic_cast<CGameEventCaused*> ( event )->getCause() )->setItem ( slot, this );
}

int CItem::getPower() const {
    return power;
}

void CItem::setPower ( int value ) {
    power = value;
}

CArmor::CArmor() {

}

CInteraction *CItem::getInteraction() {
    return interaction;
}

CBelt::CBelt() {

}

CBoots::CBoots() {

}

CGloves::CGloves() {

}

CHelmet::CHelmet() {

}

CSmallWeapon::CSmallWeapon() {

}

CWeapon::CWeapon() : CItem() {

}

Stats CItem::getBonus() {
    return bonus;
}

void CItem::setBonus ( Stats stats ) {
    this->bonus=stats;
}

QString CItem::getInteractionName() {
    if ( interaction ) {
        return interaction->getObjectType();
    }
    return "";
}

void CItem::setInteractionName ( QString name ) {
    interaction=this->getMap()->getObjectHandler()->createObject<CInteraction*> ( name );
    interaction->setManaCost ( 0 );
}

CPotion::CPotion() {

}

CScroll::CScroll() {

}

QString CScroll::getText() const {
    return text;
}

void CScroll::setText ( const QString &value ) {
    text = value;
}

void CScroll::onUse ( CGameEvent * ) {
    getMap()->getGame()->getGuiHandler()->showMessage ( text );
}

