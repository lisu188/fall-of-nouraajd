#include "stats.h"

#include <sstream>
#include <string>

Stats::Stats() {}

void Stats::setMain(const char *stat) {
  if (!stat) {
    main = &strength;
    return;
  }

  switch (stat[0]) {
  case 'A':
    main = &agility;
    break;
  case 'I':
    main = &intelligence;
    break;
  case 'S':
  default:
    main = &strength;
    break;
  }
}

int Stats::getMain() { return main ? *main : 0; }

void Stats::addBonus(Stats *stats) {
  if (!stats)
    return;

  strength += stats->getStrength();
  stamina += stats->getStamina();
  agility += stats->getAgility();
  intelligence += stats->getIntelligence();

  armor += stats->getArmor();
  block += stats->getBlock();

  dmgMin += stats->getDmgMin();
  dmgMax += stats->getDmgMax();
  hit += stats->getHit();
  crit += stats->getCrit();

  fireResist += stats->getFireResist();
  thunderResist += stats->getThunderResist();
  frostResist += stats->getFrostResist();
  normalResist += stats->getNormalResist();

  damage += stats->getDamage();
  attack += stats->getAttack();
}

void Stats::removeBonus(Stats *stats) {
  if (!stats)
    return;

  strength -= stats->getStrength();
  stamina -= stats->getStamina();
  agility -= stats->getAgility();
  intelligence -= stats->getIntelligence();

  armor -= stats->getArmor();
  block -= stats->getBlock();

  dmgMin -= stats->getDmgMin();
  dmgMax -= stats->getDmgMax();
  hit -= stats->getHit();
  crit -= stats->getCrit();

  fireResist -= stats->getFireResist();
  thunderResist -= stats->getThunderResist();
  frostResist -= stats->getFrostResist();
  normalResist -= stats->getNormalResist();

  damage -= stats->getDamage();
  attack -= stats->getAttack();
}

int Stats::getStrength() const { return strength; }

void Stats::setStrength(int value) { strength = value; }

int Stats::getStamina() const { return stamina; }

void Stats::setStamina(int value) { stamina = value; }

int Stats::getAgility() const { return agility; }

void Stats::setAgility(int value) { agility = value; }

int Stats::getIntelligence() const { return intelligence; }

void Stats::setIntelligence(int value) { intelligence = value; }

int Stats::getArmor() const { return armor; }

void Stats::setArmor(int value) { armor = value; }

int Stats::getBlock() const { return block; }

void Stats::setBlock(int value) { block = value; }

int Stats::getDmgMin() const { return dmgMin; }

void Stats::setDmgMin(int value) { dmgMin = value; }

int Stats::getDmgMax() const { return dmgMax; }

void Stats::setDmgMax(int value) { dmgMax = value; }

int Stats::getHit() const { return hit; }

void Stats::setHit(int value) { hit = value; }

int Stats::getCrit() const { return crit; }

void Stats::setCrit(int value) { crit = value; }

int Stats::getFireResist() const { return fireResist; }

void Stats::setFireResist(int value) { fireResist = value; }

int Stats::getThunderResist() const { return thunderResist; }

void Stats::setThunderResist(int value) { thunderResist = value; }

int Stats::getFrostResist() const { return frostResist; }

void Stats::setFrostResist(int value) { frostResist = value; }

int Stats::getNormalResist() const { return normalResist; }

void Stats::setNormalResist(int value) { normalResist = value; }

int Stats::getDamage() const { return damage; }

void Stats::setDamage(int value) { damage = value; }

int Stats::getAttack() const { return attack; }

void Stats::setAttack(int value) { attack = value; }

const char *Stats::getText(int level) {
  static std::string text;
  std::ostringstream stream;
  stream << "Level " << level << " S:" << getStrength() << " A:" << getAgility()
         << " I:" << getIntelligence() << " St:" << getStamina();
  text = stream.str();
  return text.c_str();
}
