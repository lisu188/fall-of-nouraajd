#pragma once

#include "CCreature.h"

class CQuest;

class CPlayer : public CCreature {
V_META(CPlayer, CCreature,
       V_PROPERTY(CPlayer, std::set<std::shared_ptr<CQuest>>, quests, getQuests, setQuests),
       V_PROPERTY(CPlayer, std::set<std::shared_ptr<CQuest>>, completedQuests, getCompletedQuests, setCompletedQuests))

public:
    CPlayer();

    virtual ~CPlayer();

    virtual void onTurn(std::shared_ptr<CGameEvent>) override;

    virtual void onDestroy(std::shared_ptr<CGameEvent> event) override;

    void addQuest(std::string questName);

    std::set<std::shared_ptr<CQuest>> getQuests();

    void setQuests(std::set<std::shared_ptr<CQuest>> quests);

private:
    void checkQuests();

    std::set<std::shared_ptr<CQuest>> quests;
    std::set<std::shared_ptr<CQuest>> completedQuests;
public:
    std::set<std::shared_ptr<CQuest>> getCompletedQuests();

    void setCompletedQuests(std::set<std::shared_ptr<CQuest>> completedQuests);

private:
    int turn = 0;
};


