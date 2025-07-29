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

#include "CGameObject.h"

class CDialogOption : public CGameObject {
  V_META(CDialogOption, CGameObject,
         V_PROPERTY(CDialogOption, int, number, getNumber, setNumber),
         V_PROPERTY(CDialogOption, std::string, nextStateId, getNextStateId,
                    setNextStateId),
         V_PROPERTY(CDialogOption, std::string, text, getText, setText),
         V_PROPERTY(CDialogOption, std::string, condition, getCondition,
                    setCondition),
         V_PROPERTY(CDialogOption, std::string, action, getAction, setAction))

public:
  int getNumber() const;

  void setNumber(int number);

  const std::string &getText() const;

  void setText(const std::string &text);

  const std::string &getAction() const;

  void setAction(const std::string &action);

private:
  std::string nextStateId;

public:
  const std::string &getNextStateId() const;

  void setNextStateId(const std::string &nextStateId);

private:
  int number;

  std::string text;
  std::string action;
  std::string condition;

public:
  const std::string &getCondition() const;

  void setCondition(const std::string &condition);
};

class CDialogState : public CGameObject {
  V_META(CDialogState, CGameObject,
         V_PROPERTY(CDialogState, std::set<std::shared_ptr<CDialogOption>>,
                    options, getOptions, setOptions),
         V_PROPERTY(CDialogState, std::string, stateId, getStateId, setStateId),
         V_PROPERTY(CDialogState, std::string, text, getText, setText))
public:
  const std::string &getText() const;

  void setText(const std::string &text);

  const std::set<std::shared_ptr<CDialogOption>> &getOptions() const;

  void setOptions(const std::set<std::shared_ptr<CDialogOption>> &options);

private:
  std::string stateId;

public:
  const std::string &getStateId() const;

  void setStateId(const std::string &stateId);

private:
  std::string text;
  std::set<std::shared_ptr<CDialogOption>> options;
};

class CDialog : public CGameObject {
  V_META(CDialog, CGameObject,
         V_PROPERTY(CDialog, std::set<std::shared_ptr<CDialogState>>, states,
                    getStates, setStates))
public:
  const std::set<std::shared_ptr<CDialogState>> &getStates() const;

  void setStates(const std::set<std::shared_ptr<CDialogState>> &states);

  std::shared_ptr<CDialogState> getState(std::string state);

  virtual void invokeAction(std::string action);

  virtual bool invokeCondition(std::string action);

private:
  std::set<std::shared_ptr<CDialogState>> states;
};