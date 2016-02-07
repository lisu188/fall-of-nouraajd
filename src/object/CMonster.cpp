#include "CMonster.h"
#include "core/CMap.h"

void CMonster::levelUp() {
    CCreature::levelUp();
    heal(0);
    addMana(0);
}

CMonster::CMonster() {

}

CMonster::~CMonster() {

}

void CMonster::onTurn(std::shared_ptr<CGameEvent>) {
    this->addExp(rand() % 25);
}
