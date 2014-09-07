#pragma once
#include "Util.h"
#include <QJsonObject>
#include <QObject>

class Stats : public QObject {
  Q_OBJECT
  PROP(int, strength, Strength)
  PROP(int, agility, Agility)
  PROP(int, stamina, Stamina)
  PROP(int, intelligence, Intelligence)
  PROP(int, armor, Armor)
  PROP(int, block, Block)
  PROP(int, dmgMin, DmgMin)
  PROP(int, dmgMax, DmgMax)
  PROP(int, hit, Hit)
  PROP(int, crit, Crit)
  PROP(int, fireResist, FireResist)
  PROP(int, frostResist, FrostResist)
  PROP(int, normalResist, NormalResist)
  PROP(int, thunderResist, ThunderResist)
  PROP(int, shadowResist, ShadowResist)
  PROP(int, damage, Damage)
  PROP(int, attack, Attack)
public:
  Stats();
  Stats(const Stats &stats);
  void operator=(const Stats &stats);
  void setMain(QString stat);
  int getMain();

  void addBonus(Stats stats);
  void removeBonus(Stats stats);

  const char *getText(int level);
  // PROPERTY_ACCESSOR
  Q_INVOKABLE void setProperty(QString name, QVariant property) {
    this->QObject::setProperty(name.toStdString().c_str(), property);
  }
  Q_INVOKABLE QVariant property(QString name) const {
    return this->QObject::property(name.toStdString().c_str());
  }
  Q_INVOKABLE void setStringProperty(QString name, QString value) {
    this->setProperty(name, value);
  }
  Q_INVOKABLE void setBoolProperty(QString name, bool value) {
    this->setProperty(name, value);
  }
  Q_INVOKABLE void setNumericProperty(QString name, int value) {
    this->setProperty(name, value);
  }
  Q_INVOKABLE QString getStringProperty(QString name) const {
    return this->property(name).toString();
  }
  Q_INVOKABLE bool getBoolProperty(QString name) const {
    return this->property(name).toBool();
  }
  Q_INVOKABLE int getNumericProperty(QString name) const {
    return this->property(name).toInt();
  }
  Q_INVOKABLE void incProperty(QString name, int value) {
    this->setNumericProperty(name, this->getNumericProperty(name) + value);
  }
  //! PROPERTY_ACCESSOR
private:
  int *main = 0;
  QString mainS;
};

class Damage : public QObject {
  Q_OBJECT
  PROP(int, fire, Fire)
  PROP(int, thunder, Thunder)
  PROP(int, shadow, Shadow)
  PROP(int, frost, Frost)
  PROP(int, normal, Normal)
public:
  Damage();
  Damage(const Damage &dmg);
  Q_INVOKABLE void setProperty(QString name, QVariant property) {
    this->QObject::setProperty(name.toStdString().c_str(), property);
  }
  Q_INVOKABLE QVariant property(QString name) const {
    return this->QObject::property(name.toStdString().c_str());
  }
  Q_INVOKABLE void setStringProperty(QString name, QString value) {
    this->setProperty(name, value);
  }
  Q_INVOKABLE void setBoolProperty(QString name, bool value) {
    this->setProperty(name, value);
  }
  Q_INVOKABLE void setNumericProperty(QString name, int value) {
    this->setProperty(name, value);
  }
  Q_INVOKABLE QString getStringProperty(QString name) const {
    return this->property(name).toString();
  }
  Q_INVOKABLE bool getBoolProperty(QString name) const {
    return this->property(name).toBool();
  }
  Q_INVOKABLE int getNumericProperty(QString name) const {
    return this->property(name).toInt();
  }
  Q_INVOKABLE void incProperty(QString name, int value) {
    this->setNumericProperty(name, this->getNumericProperty(name) + value);
  }
};
