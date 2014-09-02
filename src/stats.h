#pragma once
#include <lib/json/json.h>
#include "util.h"
#include <QObject>

#include "../gen/prop.h"

class Stats : public QObject {
	Q_OBJECT
	Q_PROPERTY ( int strength READ getStrength WRITE setStrength USER true )
	Q_PROPERTY ( int agility READ getAgility WRITE setAgility USER true )
	Q_PROPERTY ( int stamina READ getStamina WRITE setStamina USER true )
	Q_PROPERTY ( int intelligence READ getIntelligence WRITE setIntelligence
	             USER true )
	Q_PROPERTY ( int armor READ getArmor WRITE setArmor USER true )
	Q_PROPERTY ( int block READ getBlock WRITE setBlock USER true )
	Q_PROPERTY ( int dmgMin READ getDmgMin WRITE setDmgMin USER true )
	Q_PROPERTY ( int dmgMax READ getDmgMax WRITE setDmgMax USER true )
	Q_PROPERTY ( int hit READ getHit WRITE setHit USER true )
	Q_PROPERTY ( int crit READ getCrit WRITE setCrit USER true )
	Q_PROPERTY ( int fireResist READ getFireResist WRITE setFireResist USER true )
	Q_PROPERTY ( int frostResist READ getFrostResist WRITE setFrostResist
	             USER true )
	Q_PROPERTY ( int thunderResist READ getThunderResist WRITE setThunderResist
	             USER true )
	Q_PROPERTY ( int normalResist READ getNormalResist WRITE setNormalResist
	             USER true )
	Q_PROPERTY ( int shadowResist READ getShadowResist WRITE setShadowResist
	             USER true )
	Q_PROPERTY ( int damage READ getDamage() WRITE setDamage USER true )
	Q_PROPERTY ( int attack READ getAttack() WRITE setAttack USER true )
public:
	Stats();
	Stats ( const Stats &stats );
	void setMain ( const char *stat );
	int getMain();

	void addBonus ( Stats stats );
	void removeBonus ( Stats stats );

	int getStrength() const;
	void setStrength ( int value );

	int getStamina() const;
	void setStamina ( int value );

	int getAgility() const;
	void setAgility ( int value );

	int getIntelligence() const;
	void setIntelligence ( int value );

	int getArmor() const;
	void setArmor ( int value );

	int getBlock() const;
	void setBlock ( int value );

	int getDmgMin() const;
	void setDmgMin ( int value );

	int getDmgMax() const;
	void setDmgMax ( int value );

	int getHit() const;
	void setHit ( int value );

	int getCrit() const;
	void setCrit ( int value );

	int getFireResist() const;
	void setFireResist ( int value );

	int getThunderResist() const;
	void setThunderResist ( int value );

	int getFrostResist() const;
	void setFrostResist ( int value );

	int getNormalResist() const;
	void setNormalResist ( int value );

	int getDamage() const;
	void setDamage ( int value );

	int getAttack() const;
	void setAttack ( int value );

	const char *getText ( int level );
	void loadFromJson ( Json::Value config );
	Json::Value saveToJson();

	int getShadowResist() const;
	void setShadowResist ( int value );

	PROPERTY_ACCESSOR
private:
	int strength = 0;
	int stamina = 0;
	int agility = 0;
	int intelligence = 0;
	int armor = 0;
	int block = 0;
	int dmgMin = 0;
	int dmgMax = 0;
	int hit = 0;
	int crit = 0;
	int fireResist = 0;
	int thunderResist = 0;
	int frostResist = 0;
	int normalResist = 0;
	int shadowResist = 0;
	int damage = 0;
	int attack = 0;
	int *main = 0;
	std::string mainS;
	int m_strength;
	int m_fireResist;
};

class Damage : public QObject {
	Q_OBJECT
public:
	Damage();
	Damage ( const Damage &dmg );
	PROPERTY_ACCESSOR
private:
	_Damage
//	PROP ( int,fire,Fire )
//	PROP ( int,thunder,Thunder )
//	PROP ( int,frost,Frost )
//	PROP ( int,normal ,Normal )
//	PROP ( int,shadow ,Shadow )
};
