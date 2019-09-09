//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
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


