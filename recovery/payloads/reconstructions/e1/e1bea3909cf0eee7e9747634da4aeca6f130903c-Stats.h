// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
// Missing original header reconstructed from the intact adjacent generator inputs.
#pragma once
#include "Util.h"
#include <QJsonObject>
#include <QObject>

class Stats : public QObject {
    Q_OBJECT
  private:
    Q_PROPERTY(int strength READ getStrength WRITE setStrength USER true)
    int strength = 0;

  public:
    int getStrength() { return strength; }
    void setStrength(int value) { this->strength = value; }

  private:
  private:
    Q_PROPERTY(int agility READ getAgility WRITE setAgility USER true)
    int agility = 0;

  public:
    int getAgility() { return agility; }
    void setAgility(int value) { this->agility = value; }

  private:
  private:
    Q_PROPERTY(int stamina READ getStamina WRITE setStamina USER true)
    int stamina = 0;

  public:
    int getStamina() { return stamina; }
    void setStamina(int value) { this->stamina = value; }

  private:
  private:
    Q_PROPERTY(int intelligence READ getIntelligence WRITE setIntelligence USER true)
    int intelligence = 0;

  public:
    int getIntelligence() { return intelligence; }
    void setIntelligence(int value) { this->intelligence = value; }

  private:
  private:
    Q_PROPERTY(int armor READ getArmor WRITE setArmor USER true)
    int armor = 0;

  public:
    int getArmor() { return armor; }
    void setArmor(int value) { this->armor = value; }

  private:
  private:
    Q_PROPERTY(int block READ getBlock WRITE setBlock USER true)
    int block = 0;

  public:
    int getBlock() { return block; }
    void setBlock(int value) { this->block = value; }

  private:
  private:
    Q_PROPERTY(int dmgMin READ getDmgMin WRITE setDmgMin USER true)
    int dmgMin = 0;

  public:
    int getDmgMin() { return dmgMin; }
    void setDmgMin(int value) { this->dmgMin = value; }

  private:
  private:
    Q_PROPERTY(int dmgMax READ getDmgMax WRITE setDmgMax USER true)
    int dmgMax = 0;

  public:
    int getDmgMax() { return dmgMax; }
    void setDmgMax(int value) { this->dmgMax = value; }

  private:
  private:
    Q_PROPERTY(int hit READ getHit WRITE setHit USER true)
    int hit = 0;

  public:
    int getHit() { return hit; }
    void setHit(int value) { this->hit = value; }

  private:
  private:
    Q_PROPERTY(int crit READ getCrit WRITE setCrit USER true)
    int crit = 0;

  public:
    int getCrit() { return crit; }
    void setCrit(int value) { this->crit = value; }

  private:
  private:
    Q_PROPERTY(int fireResist READ getFireResist WRITE setFireResist USER true)
    int fireResist = 0;

  public:
    int getFireResist() { return fireResist; }
    void setFireResist(int value) { this->fireResist = value; }

  private:
  private:
    Q_PROPERTY(int frostResist READ getFrostResist WRITE setFrostResist USER true)
    int frostResist = 0;

  public:
    int getFrostResist() { return frostResist; }
    void setFrostResist(int value) { this->frostResist = value; }

  private:
  private:
    Q_PROPERTY(int normalResist READ getNormalResist WRITE setNormalResist USER true)
    int normalResist = 0;

  public:
    int getNormalResist() { return normalResist; }
    void setNormalResist(int value) { this->normalResist = value; }

  private:
  private:
    Q_PROPERTY(int thunderResist READ getThunderResist WRITE setThunderResist USER true)
    int thunderResist = 0;

  public:
    int getThunderResist() { return thunderResist; }
    void setThunderResist(int value) { this->thunderResist = value; }

  private:
  private:
    Q_PROPERTY(int shadowResist READ getShadowResist WRITE setShadowResist USER true)
    int shadowResist = 0;

  public:
    int getShadowResist() { return shadowResist; }
    void setShadowResist(int value) { this->shadowResist = value; }

  private:
  private:
    Q_PROPERTY(int damage READ getDamage WRITE setDamage USER true)
    int damage = 0;

  public:
    int getDamage() { return damage; }
    void setDamage(int value) { this->damage = value; }

  private:
  private:
    Q_PROPERTY(int attack READ getAttack WRITE setAttack USER true)
    int attack = 0;

  public:
    int getAttack() { return attack; }
    void setAttack(int value) { this->attack = value; }

  private:
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
    Q_INVOKABLE QVariant property(QString name) const { return this->QObject::property(name.toStdString().c_str()); }
    Q_INVOKABLE void setStringProperty(QString name, QString value) { this->setProperty(name, value); }
    Q_INVOKABLE void setBoolProperty(QString name, bool value) { this->setProperty(name, value); }
    Q_INVOKABLE void setNumericProperty(QString name, int value) { this->setProperty(name, value); }
    Q_INVOKABLE QString getStringProperty(QString name) const { return this->property(name).toString(); }
    Q_INVOKABLE bool getBoolProperty(QString name) const { return this->property(name).toBool(); }
    Q_INVOKABLE int getNumericProperty(QString name) const { return this->property(name).toInt(); }
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
  private:
    Q_PROPERTY(int fire READ getFire WRITE setFire USER true)
    int fire = 0;

  public:
    int getFire() { return fire; }
    void setFire(int value) { this->fire = value; }

  private:
  private:
    Q_PROPERTY(int thunder READ getThunder WRITE setThunder USER true)
    int thunder = 0;

  public:
    int getThunder() { return thunder; }
    void setThunder(int value) { this->thunder = value; }

  private:
  private:
    Q_PROPERTY(int shadow READ getShadow WRITE setShadow USER true)
    int shadow = 0;

  public:
    int getShadow() { return shadow; }
    void setShadow(int value) { this->shadow = value; }

  private:
  private:
    Q_PROPERTY(int frost READ getFrost WRITE setFrost USER true)
    int frost = 0;

  public:
    int getFrost() { return frost; }
    void setFrost(int value) { this->frost = value; }

  private:
  private:
    Q_PROPERTY(int normal READ getNormal WRITE setNormal USER true)
    int normal = 0;

  public:
    int getNormal() { return normal; }
    void setNormal(int value) { this->normal = value; }

  private:
  public:
    Damage();
    Damage(const Damage &dmg);
    Q_INVOKABLE void setProperty(QString name, QVariant property) {
        this->QObject::setProperty(name.toStdString().c_str(), property);
    }
    Q_INVOKABLE QVariant property(QString name) const { return this->QObject::property(name.toStdString().c_str()); }
    Q_INVOKABLE void setStringProperty(QString name, QString value) { this->setProperty(name, value); }
    Q_INVOKABLE void setBoolProperty(QString name, bool value) { this->setProperty(name, value); }
    Q_INVOKABLE void setNumericProperty(QString name, int value) { this->setProperty(name, value); }
    Q_INVOKABLE QString getStringProperty(QString name) const { return this->property(name).toString(); }
    Q_INVOKABLE bool getBoolProperty(QString name) const { return this->property(name).toBool(); }
    Q_INVOKABLE int getNumericProperty(QString name) const { return this->property(name).toInt(); }
    Q_INVOKABLE void incProperty(QString name, int value) {
        this->setNumericProperty(name, this->getNumericProperty(name) + value);
    }
};
