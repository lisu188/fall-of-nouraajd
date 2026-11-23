#include "Stats.h"

#include <QMetaProperty>
#include <sstream>

Stats::Stats() {
  for (int i = 0; i < metaObject()->propertyCount(); ++i) {
    QMetaProperty property = metaObject()->property(i);
    if (property.isUser())
      setNumericProperty(property.name(), 0);
  }
}

Stats::Stats(const Stats &stats) : Stats() {
  for (int i = 0; i < metaObject()->propertyCount(); ++i) {
    QMetaProperty property = metaObject()->property(i);
    if (property.isUser())
      setNumericProperty(property.name(),
                         stats.getNumericProperty(property.name()));
  }
  setMain(stats.mainS);
}

void Stats::setMain(QString stat) {
  mainS = stat;
  main = nullptr;
  QString normalized = stat.toLower();
  if (normalized == "agility")
    main = &agility;
  else if (normalized == "intelligence")
    main = &intelligence;
  else if (normalized == "strength")
    main = &strength;
}

int Stats::getMain() {
  if (!main) {
    return 0;
  }
  return *main;
}

void Stats::addBonus(Stats stats) {
  for (int i = 0; i < this->metaObject()->propertyCount(); i++) {
    QMetaProperty property = this->metaObject()->property(i);
    this->incProperty(property.name(),
                      stats.getNumericProperty(property.name()));
  }
}

void Stats::removeBonus(Stats stats) {
  for (int i = 0; i < this->metaObject()->propertyCount(); i++) {
    QMetaProperty property = this->metaObject()->property(i);
    this->incProperty(property.name(),
                      -stats.getNumericProperty(property.name()));
  }
}

const char *Stats::getText(int level) {
  std::ostringstream stream;
  stream << "Level: " << level << "\n";
  stream << "Strength: " << strength << "\n";
  stream << "Agility: " << agility << "\n";
  stream << "Intelligence: " << intelligence << "\n";
  stream << "Stamina: " << stamina << "\n";
  stream << "Damage: " << dmgMin + damage << "-" << dmgMax + damage << "\n";
  stream << "Hit: " << hit + attack << "%" << "\n";
  stream << "Crit: " << crit << "%" << "\n";
  stream << "Armor: " << armor << "%" << "\n";
  stream << "Block: " << block << "%" << "\n";
  static thread_local std::string text;
  text = stream.str();
  return text.c_str();
}

Damage::Damage() {
  for (int i = 0; i < this->metaObject()->propertyCount(); i++) {
    QMetaProperty property = this->metaObject()->property(i);
    this->setNumericProperty(property.name(), 0);
  }
}

Damage::Damage(const Damage &dmg) {
  for (int i = 0; i < this->metaObject()->propertyCount(); i++) {
    QMetaProperty property = this->metaObject()->property(i);
    this->setNumericProperty(property.name(),
                             dmg.getNumericProperty(property.name()));
  }
}

void Stats::loadFromJson(QJsonObject config) {
  for (auto it = config.begin(); it != config.end(); ++it) {
    if (it.key() == "main") {
      setMain(it.value().toString());
      continue;
    }
    int index = metaObject()->indexOfProperty(it.key().toUtf8().constData());
    if (index >= 0 && metaObject()->property(index).isUser() &&
        it.value().isDouble())
      setNumericProperty(it.key(), it.value().toInt());
  }
}
QJsonObject Stats::saveToJson() {
  QJsonObject result;
  for (int i = 0; i < metaObject()->propertyCount(); ++i) {
    QMetaProperty property = metaObject()->property(i);
    if (property.isUser())
      result[property.name()] = getNumericProperty(property.name());
  }
  if (!mainS.isEmpty())
    result["main"] = mainS;
  return result;
}
