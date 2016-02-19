#pragma once

#include "CCreature.h"

class CQuest;

class CPlayer : public CCreature {
V_META(CPlayer, CCreature, vstd::meta::empty())

public:
    CPlayer();

    CPlayer(const CPlayer &);

    virtual ~CPlayer();

    virtual void onTurn(std::shared_ptr<CGameEvent>) override;

    virtual void onDestroy(std::shared_ptr<CGameEvent> event) override;

    virtual std::shared_ptr<CInteraction> selectAction() override;

    //TODO: implement
//    virtual void fight(std::shared_ptr<CCreature> creature) override;

    virtual void trade(std::shared_ptr<CMarket> object) override;

    std::shared_ptr<CInteraction> getSelectedAction() const;

    void setSelectedAction(std::shared_ptr<CInteraction> value);

    std::shared_ptr<CCreature> getEnemy() const;

    void setEnemy(std::shared_ptr<CCreature> value);

    void setNextMove(Coords coords);

    std::shared_ptr<CMarket> getMarket() const;

    void setMarket(std::shared_ptr<CMarket> value);

    void addQuest(std::string questName);

private:
    void checkQuests();

    std::shared_ptr<CInteraction> selectedAction;
    std::shared_ptr<CCreature> enemy;
    std::shared_ptr<CMarket> market;
    std::set<std::shared_ptr<CQuest>> quests;
    int turn = 0;
    Coords next;
};


