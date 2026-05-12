/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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

#include "CGameObject.h"

class CQuest : public CGameObject {
    V_META(CQuest, CGameObject, V_PROPERTY(CQuest, std::string, description, getDescription, setDescription),
           V_PROPERTY(CQuest, std::string, objective, getObjective, setObjective),
           V_PROPERTY(CQuest, std::string, reward, getReward, setReward),
           V_PROPERTY(CQuest, std::string, hint, getHint, setHint))
  public:
    CQuest();

    virtual bool isCompleted();

    virtual void onComplete();

    virtual std::string getObjective();

    virtual std::string getReward();

    virtual std::string getHint();

    std::string getDescription();

    void setDescription(std::string description);

    void setObjective(std::string objective);

    void setReward(std::string reward);

    void setHint(std::string hint);

  private:
    std::string description = "";
    std::string objective = "";
    std::string reward = "";
    std::string hint = "";
};
