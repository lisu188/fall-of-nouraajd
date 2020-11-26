/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2020  Andrzej Lis

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

#include "CGamePanel.h"

class CDialog;

class CDialogOption;

class CGameDialogPanel : public CGamePanel {
V_META(CGameDialogPanel, CGamePanel,
       V_PROPERTY(CGameDialogPanel, std::shared_ptr<CDialog>, dialog, getDialog, setDialog))
public:
    const std::shared_ptr<CDialog> &getDialog() const;

    void setDialog(const std::shared_ptr<CDialog> &dialog);

    void reload();

    bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) override;

private:
    std::shared_ptr<CDialog> dialog;
    std::string currentStateId = "ENTRY";

    std::shared_ptr<CDialogOption> getOption(int option);

    void selectOption(int option);

    void selectOption(const std::shared_ptr<CDialogOption> &option);

    const std::set<std::shared_ptr<CDialogOption>> &getCurrentOptions();
};

