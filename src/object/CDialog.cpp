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
#include "CDialog.h"

const std::set<std::shared_ptr<CDialogState>> &CDialog::getStates() const {
    return states;
}

void CDialog::setStates(const std::set<std::shared_ptr<CDialogState>> &states) {
    CDialog::states = states;
}

std::shared_ptr<CDialogState> CDialog::getState(int state) {
    return vstd::find_if(states, [state](auto _state) { return _state->getNumber() == state; });
}


int CDialogState::getNumber() const {
    return number;
}

void CDialogState::setNumber(int number) {
    CDialogState::number = number;
}

const std::string &CDialogState::getText() const {
    return text;
}

void CDialogState::setText(const std::string &text) {
    CDialogState::text = text;
}

const std::set<std::shared_ptr<CDialogOption>> &CDialogState::getOptions() const {
    return options;
}

void CDialogState::setOptions(const std::set<std::shared_ptr<CDialogOption>> &options) {
    CDialogState::options = options;
}

int CDialogOption::getNumber() const {
    return number;
}

void CDialogOption::setNumber(int number) {
    CDialogOption::number = number;
}

int CDialogOption::getNext() const {
    return next;
}

void CDialogOption::setNext(int next) {
    CDialogOption::next = next;
}

const std::string &CDialogOption::getText() const {
    return text;
}

void CDialogOption::setText(const std::string &text) {
    CDialogOption::text = text;
}

const std::string &CDialogOption::getAction() const {
    return action;
}

void CDialogOption::setAction(const std::string &action) {
    CDialogOption::action = action;
}