#pragma once

#include "CMapObject.h"
#include "core/CStats.h"

class CCreature;

class CInteraction;

class CItem : public CMapObject, public Visitable, public Wearable, public Usable {

V_META(CItem, CMapObject,
       V_PROPERTY(CItem, int, power, getPower, setPower),
       V_PROPERTY(CItem, std::shared_ptr<Stats>, bonus, getBonus, setBonus),
       V_PROPERTY(CItem, std::shared_ptr<CInteraction>, interaction, getInteraction, setInteraction)
)

public:
    CItem();

    virtual ~CItem();

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

    virtual bool isDisposable();

protected:
    std::shared_ptr<Stats> bonus = std::make_shared<Stats>();
    std::shared_ptr<CInteraction> interaction;
    int power = 0;
private:
    int slot = 0;
};


class CArmor : public CItem {
V_META(CArmor, CItem, vstd::meta::empty())
public:
    CArmor();

    CArmor(const CArmor &);

    CArmor(std::string name);
};


class CBelt : public CItem {
V_META(CBelt, CItem, vstd::meta::empty())
public:
    CBelt();

    CBelt(const CBelt &);
};


class CHelmet : public CItem {
V_META(CHelmet, CItem, vstd::meta::empty())
public:
    CHelmet();

    CHelmet(const CHelmet &);
};


class CBoots : public CItem {
V_META(CBoots, CItem, vstd::meta::empty())
public:
    CBoots();

    CBoots(const CBoots &);
};


class CGloves : public CItem {
V_META(CGloves, CItem, vstd::meta::empty())
public:
    CGloves();

    CGloves(const CGloves &);
};


class CWeapon : public CItem {
V_META(CWeapon, CItem, vstd::meta::empty())
public:
    CWeapon();

    CWeapon(const CWeapon &);
};


class CSmallWeapon : public CWeapon {
V_META(CSmallWeapon, CWeapon, vstd::meta::empty())
public:
    CSmallWeapon();

    CSmallWeapon(const CSmallWeapon &);
};


class CScroll : public CItem {

V_META(CScroll, CItem,
       V_PROPERTY(CScroll, std::string, text, getText, setText)
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


class CPotion : public CItem {
V_META(CPotion, CItem, vstd::meta::empty())

public:
    bool isDisposable() override;

    CPotion();

    CPotion(const CPotion &);
};

