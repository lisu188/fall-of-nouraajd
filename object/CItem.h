#pragma once
#include "CMapObject.h"
#include "CStats.h"

class CCreature;
class CInteraction;

class CItem : public CMapObject,public Visitable,public Wearable,public Usable {
    Q_OBJECT
    Q_PROPERTY ( int power READ getPower WRITE setPower USER true )
    Q_PROPERTY ( bool singleUse READ isSingleUse WRITE setSingleUse USER true )
    Q_PROPERTY ( std::shared_ptr<Stats> bonus READ getBonus WRITE setBonus USER true )
    Q_PROPERTY ( std::shared_ptr<CInteraction> interaction READ getInteraction WRITE setInteraction )
public:
    CItem();
    virtual ~CItem();
    bool isSingleUse();
    void setSingleUse ( bool singleUse );

    virtual void onEquip ( std::shared_ptr<CGameEvent> event ) override;
    virtual void onUnequip ( std::shared_ptr<CGameEvent> event ) override;

    virtual void onUse ( std::shared_ptr<CGameEvent> event ) override;

    virtual void onEnter ( std::shared_ptr<CGameEvent> event ) override;
    virtual void onLeave ( std::shared_ptr<CGameEvent> ) override;

    int getPower() const;
    void setPower ( int value );
    std::shared_ptr<Stats> getBonus();
    void setBonus ( std::shared_ptr<Stats> stats );
    std::shared_ptr<CInteraction> getInteraction();
    void setInteraction ( std::shared_ptr<CInteraction> interaction );
protected:
    bool singleUse=false;
    std::shared_ptr<Stats> bonus=std::make_shared<Stats>();
    std::shared_ptr<CInteraction> interaction;
    int power=0;
private:
    int slot = 0;
};
GAME_PROPERTY ( CItem )

class CArmor : public CItem {
    Q_OBJECT
public:
    CArmor();
    CArmor ( const CArmor & );
    CArmor ( QString name );
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
};

class CSmallWeapon : public CWeapon {
    Q_OBJECT
public:
    CSmallWeapon();
    CSmallWeapon ( const CSmallWeapon & );
};

class CScroll : public CItem {
    Q_OBJECT
    Q_PROPERTY ( QString text READ getText WRITE setText USER true )
public:
    CScroll();
    CScroll ( const CScroll & );
    QString getText() const;
    void setText ( const QString &value );
    virtual void onUse ( std::shared_ptr<CGameEvent>  ) override;
private:
    QString text;
};

class CPotion : public CItem {
    Q_OBJECT
public:
    CPotion();
    CPotion ( const CPotion & );
};
