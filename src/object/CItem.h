#pragma once

#include "CMapObject.h"
#include "core/CStats.h"

class CCreature;

class CInteraction;

class CItem : public CMapObject, public Visitable, public Wearable, public Usable {

V_META(CItem, CMapObject,
       V_PROPERTY(CItem, int, power, getPower, setPower),
       V_PROPERTY(CItem, std::shared_ptr<Stats>, bonus, getBonus, setBonus),
       V_PROPERTY(CItem, bool, singleUse, isSingleUse, setSingleUse),
       V_PROPERTY(CItem, std::shared_ptr<CInteraction>, interaction, getInteraction, setInteraction)
)

public:
    CItem();

    virtual ~CItem();

    bool isSingleUse();

    void setSingleUse(bool singleUse);

    virtual void onEquip(std::shared_ptr<CGameEvent> event) override;

    virtual void onUnequip(std::shared_ptr<CGameEvent> event) override;

    virtual void onUse(std::shared_ptr<CGameEvent> event) override;

    virtual void onEnter(std::shared_ptr<CGameEvent> event) override;

    virtual void onLeave(std::shared_ptr<CGameEvent>) override;

    int getPower() const;

    void setPower(int value);

    std::shared_ptr<Stats> getBonus();

    void setBonus(std::shared_ptr<Stats> stats);

    std::shared_ptr<CInteraction> getInteraction();

    void setInteraction(std::shared_ptr<CInteraction> interaction);

protected:
    bool singleUse = false;
    std::shared_ptr<Stats> bonus = std::make_shared<Stats>();
    std::shared_ptr<CInteraction> interaction;
    int power = 0;
private:
    int slot = 0;
};

GAME_PROPERTY (CItem)

class CArmor : public CItem {

public:
    CArmor();

    CArmor(const CArmor &);

    CArmor(std::string name);
};

GAME_PROPERTY (CArmor)

class CBelt : public CItem {

public:
    CBelt();

    CBelt(const CBelt &);
};

GAME_PROPERTY (CBelt)

class CHelmet : public CItem {

public:
    CHelmet();

    CHelmet(const CHelmet &);
};

GAME_PROPERTY (CHelmet)

class CBoots : public CItem {

public:
    CBoots();

    CBoots(const CBoots &);
};

GAME_PROPERTY (CBoots)

class CGloves : public CItem {

public:
    CGloves();

    CGloves(const CGloves &);
};

GAME_PROPERTY (CGloves)

class CWeapon : public CItem {

public:
    CWeapon();

    CWeapon(const CWeapon &);
};

GAME_PROPERTY (CWeapon)

class CSmallWeapon : public CWeapon {

public:
    CSmallWeapon();

    CSmallWeapon(const CSmallWeapon &);
};

GAME_PROPERTY (CSmallWeapon)

class CScroll : public CItem {

V_META(CScroll, CItem,
       V_PROPERTY(CItem, std::string, text, getText, setText)
)

public:
    CScroll();

    CScroll(const CScroll &);

    std::string getText() const;

    void setText(const std::string &value);

    virtual void onUse(std::shared_ptr<CGameEvent>) override;

private:
    std::string text;
};

GAME_PROPERTY (CScroll)

class CPotion : public CItem {

public:
    CPotion();

    CPotion(const CPotion &);
};

GAME_PROPERTY (CPotion)
