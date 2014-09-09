#pragma once
#include "CMapObject.h"
#include "Stats.h"

class CCreature;
class CInteraction;

class CItem : public CMapObject {
	Q_OBJECT
	Q_PROPERTY ( int power READ getPower WRITE setPower USER true )
	Q_PROPERTY ( bool singleUse READ isSingleUse WRITE setSingleUse USER true )
	Q_PROPERTY ( Stats bonus READ getBonus WRITE setBonus USER true )
public:
	CItem();
	CItem ( const CItem & );
	bool isSingleUse();
	void setSingleUse ( bool singleUse );
	virtual void onEquip ( CCreature *creature );
	virtual void onUnequip ( CCreature *creature );
	static CItem *createItem ( QString name );
	virtual void onUse ( CCreature *creature );
	virtual void onEnter();
	virtual void onMove();
	int getPower() const;
	void setPower ( int value );
	Stats getBonus();
	void setBonus ( Stats stats );

protected:
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
	bool singleUse=false;
	Stats bonus;
	void loadFromJson ( QString name );
	CInteraction *interaction;
	int power=0;

private:
	int slot = 0;
};

class CArmor : public CItem {
	Q_OBJECT
public:
	CArmor();
	CArmor ( const CArmor & );
	CArmor ( QString name );
	CInteraction *getInteraction();
};

class CBelt : public CItem {
	Q_OBJECT
public:
	CBelt();
	CBelt ( const CBelt & );
};

class CHelmet : public CItem {
	Q_OBJECT
public:
	CHelmet();
	CHelmet ( const CHelmet & );
};

class CBoots : public CItem {
	Q_OBJECT
public:
	CBoots();
	CBoots ( const CBoots & );
};

class CGloves : public CItem {
	Q_OBJECT
public:
	CGloves();
	CGloves ( const CGloves & );
};

class CWeapon : public CItem {
	Q_OBJECT
public:
	CWeapon();
	CWeapon ( const CWeapon & );
	CInteraction *getInteraction();
};

class CSmallWeapon : public CWeapon {
	Q_OBJECT
public:
	CSmallWeapon();
	CSmallWeapon ( const CSmallWeapon & );
};

class CPotion : public CItem {
	Q_OBJECT
public:
	CPotion();
	CPotion ( const CPotion & );
	virtual void onUse ( CCreature *creature );
	virtual void loadFromJson ( QString name );

private:
	std::function<void ( CCreature *, int ) > effect;
};

void LifeEffect ( CCreature *creature, int power );
void ManaEffect ( CCreature *creature, int power );
