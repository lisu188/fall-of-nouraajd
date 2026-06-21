/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

#include "CCreature.h"

class CQuest;

class CPlayer : public CCreature {
    V_META(CPlayer, CCreature, V_PROPERTY(CPlayer, std::set<std::shared_ptr<CQuest>>, quests, getQuests, setQuests),
           V_PROPERTY(CPlayer, std::set<std::shared_ptr<CQuest>>, completedQuests, getCompletedQuests,
                      setCompletedQuests),
           V_PROPERTY(CPlayer, std::string, playerClassId, getPlayerClassId, setPlayerClassId),
           V_PROPERTY(CPlayer, std::string, raceId, getRaceId, setRaceId))

  public:
    CPlayer() = default;

    ~CPlayer() override = default;

    void addQuest(std::string questName);

    std::set<std::shared_ptr<CQuest>> getQuests();

    void setQuests(std::set<std::shared_ptr<CQuest>> quests);

    std::set<std::shared_ptr<CQuest>> getCompletedQuests();

    void setCompletedQuests(std::set<std::shared_ptr<CQuest>> completedQuests);

    std::string getPlayerClassId();

    void setPlayerClassId(std::string playerClassId);

    std::string getRaceId();

    void setRaceId(std::string raceId);

    void checkQuests();

    void incTurn();

  private:
    std::set<std::shared_ptr<CQuest>> quests;
    std::set<std::shared_ptr<CQuest>> completedQuests;
    std::string playerClassId;
    std::string raceId;

    int turn = 0;
};
