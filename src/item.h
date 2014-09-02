#pragma once
#include "CMapObject.h"
#include "stats.h"

class CCreature;
class CInteraction;

class Item : public CMapObject {
	Q_OBJECT
	Q_PROPERTY ( int power READ getPower WRITE setPower USER true )
	Q_PROPERTY ( bool singleUse READ isSingleUse WRITE setSingleUse USER true )
public:
	Item();
	Item ( const Item & );
	bool isSingleUse();
	void setSingleUse ( bool singleUse );
	virtual void onEquip ( CCreature *creature );
	virtual void onUnequip ( CCreature *creature );
	static Item *createItem ( QString name );
	virtual void onUse ( CCreature *creature );
	virtual void onEnter();
	virtual void onMove();
	int getPower() const;
	void setPower ( int value );

protected:
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
	bool singleUse;
	Stats bonus;
	void loadFromJson ( std::string name );
	CInteraction *interaction;
	int power;

private:
	int slot = 0;
};

class Armor : public Item {
	Q_OBJECT
public:
	Armor();
	Armor ( const Armor &armor );
	Armor ( std::string name );
	CInteraction *getInteraction();
};

class Belt : public Item {
	Q_OBJECT
public:
	Belt();
	Belt ( const Belt &belt );
};

class Helmet : public Item {
	Q_OBJECT
public:
	Helmet();
	Helmet ( const Helmet &helmet );
};

class Boots : public Item {
	Q_OBJECT
public:
	Boots();
	Boots ( const Boots &boots );
};

class Gloves : public Item {
	Q_OBJECT
public:
	Gloves();
	Gloves ( const Gloves &gloves );
};

class Weapon : public Item {
	Q_OBJECT
public:
	Weapon();
	Weapon ( const Weapon &weapon );
	CInteraction *getInteraction();
	Stats *getStats();
};

class SmallWeapon : public Weapon {
	Q_OBJECT
public:
	SmallWeapon();
	SmallWeapon ( const SmallWeapon &weapon );
};

