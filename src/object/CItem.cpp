#include "CItem.h"
#include "core/CGame.h"

CItem::CItem() {
    this->setZValue ( 2 );
}

CItem::~CItem() {

}

void CItem::onEnter ( std::shared_ptr<CGameEvent> event ) {
    if ( std::shared_ptr<CCreature> visitor = vstd::cast<CCreature> ( vstd::cast<CGameEventCaused> ( event )->getCause() ) ) {
        this->getMap()->removeObject ( this->ptr<CMapObject>() );
        visitor->addItem ( this->ptr<CItem>() );
    }
}

void CItem::onLeave ( std::shared_ptr<CGameEvent> ) {

}

bool CItem::isSingleUse() {
    return singleUse;
}

void CItem::setSingleUse ( bool singleUse ) {
    this->singleUse = singleUse;
}

void CItem::onEquip ( std::shared_ptr<CGameEvent> event ) {
    vstd::cast<CCreature> ( vstd::cast<CGameEventCaused> ( event )->getCause() )->addBonus ( bonus );
    qDebug() << vstd::cast<CGameEventCaused> ( event )->getCause()->getObjectType() << "equipped" << getObjectType()
             << "\n";
}

void CItem::onUnequip ( std::shared_ptr<CGameEvent> event ) {
    vstd::cast<CCreature> ( vstd::cast<CGameEventCaused> ( event )->getCause() )->removeBonus ( bonus );
    qDebug() << vstd::cast<CGameEventCaused> ( event )->getCause()->getObjectType() << "unequipped" << getObjectType()
             << "\n";
}

void CItem::onUse ( std::shared_ptr<CGameEvent> event ) {
    CItemSlot *parent = dynamic_cast<CItemSlot *> ( this->parentItem() );
    if ( !parent ) {
        return;
    }
    std::string slot = parent->getNumber();
    if ( slot == "-1" ) {
        return;
    }
    vstd::cast<CCreature> ( vstd::cast<CGameEventCaused> ( event )->getCause() )->setItem ( slot, this->ptr<CItem>() );
}

int CItem::getPower() const {
    return power;
}

void CItem::setPower ( int value ) {
    power = value;
}

CArmor::CArmor() {

}

std::shared_ptr<CInteraction> CItem::getInteraction() {
    return interaction;
}

void CItem::setInteraction ( std::shared_ptr<CInteraction> interaction ) {
    this->interaction = interaction;
    interaction->setManaCost ( 0 );
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

std::shared_ptr<Stats> CItem::getBonus() {
    return bonus;
}

void CItem::setBonus ( std::shared_ptr<Stats> stats ) {
    bonus = stats;
}

CPotion::CPotion() {

}

CScroll::CScroll() {

}

std::string CScroll::getText() const {
    return text;
}

void CScroll::setText ( const std::string &value ) {
    text = value;
}

void CScroll::onUse ( std::shared_ptr<CGameEvent> ) {
    getMap()->getGame()->getGuiHandler()->showMessage ( text );
}
