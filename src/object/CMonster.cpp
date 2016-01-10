#include "CMonster.h"
#include "core/CMap.h"
#include "core/CPathFinder.h"

void CMonster::levelUp() {
    CCreature::levelUp();
    heal(0);
    addMana(0);
}

Coords CMonster::getNextMove() {
    return CSmartPathFinder::findNextStep(this->getCoords(),
                                          this->getMap()->getPlayer() ? this->getMap()->getPlayer()->getCoords()
                                                                      : this->getCoords(),
                                          [this](const Coords &coords) {
                                              return this->getMap()->canStep(coords);
                                          })->get() - this->getCoords();
}

CMonster::CMonster() {

}

CMonster::~CMonster() {

}

void CMonster::onTurn(std::shared_ptr<CGameEvent>) {
    this->addExp(rand() % 25);
}
