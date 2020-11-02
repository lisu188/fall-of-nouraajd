/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
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

    ~CItem() override;

    void onEquip(std::shared_ptr<CGameEvent> event) override;

    void onUnequip(std::shared_ptr<CGameEvent> event) override;

    void onUse(std::shared_ptr<CGameEvent> event) override;

    void onEnter(std::shared_ptr<CGameEvent> event) override;

    void onLeave(std::shared_ptr<CGameEvent>) override;

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
};


class CBelt : public CItem {
V_META(CBelt, CItem, vstd::meta::empty())
public:
    CBelt();
};


class CHelmet : public CItem {
V_META(CHelmet, CItem, vstd::meta::empty())
public:
    CHelmet();
};


class CBoots : public CItem {
V_META(CBoots, CItem, vstd::meta::empty())
public:
    CBoots();
};


class CGloves : public CItem {
V_META(CGloves, CItem, vstd::meta::empty())
public:
    CGloves();
};


class CWeapon : public CItem {
V_META(CWeapon, CItem, vstd::meta::empty())
public:
    CWeapon();
};


class CSmallWeapon : public CWeapon {
V_META(CSmallWeapon, CWeapon, vstd::meta::empty())
public:
    CSmallWeapon();
};


class CScroll : public CItem {

V_META(CScroll, CItem,
       V_PROPERTY(CScroll, std::string, text, getText, setText)
)

public:
    CScroll();

    std::string getText() const;

    void setText(const std::string &value);

    void onUse(std::shared_ptr<CGameEvent>) override;

private:
    std::string text;
};


class CPotion : public CItem {
V_META(CPotion, CItem, vstd::meta::empty())

public:
    bool isDisposable() override;

    CPotion();
};

