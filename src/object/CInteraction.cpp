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
#include "CInteraction.h"
#include "core/CGame.h"
#include "core/CPythonOverrides.h"

CInteraction::CInteraction() {}

CInteraction::~CInteraction() {}

void CInteraction::onAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) {
    if (!first) {
        vstd::logger::warning("Skipping interaction without actor:", this->to_string());
        return;
    }

    vstd::logger::debug(first->to_string(), "used", this->to_string(), "against",
                        second ? second->to_string() : "<no target>");

    first->takeMana(this->getManaCost());

    this->performAction(first, second);

    if (effect) {
        std::shared_ptr<CEffect> effect = this->effect->clone<CEffect>();
        effect->setCaster(first);
        if (this->configureEffect(effect)) {
            if (effect->getAnimation().empty()) {
                effect->setAnimation(getAnimation());
            }
            if (effect->getLabel().empty()) {
                effect->setLabel(getLabel());
            }
            if (effectRoutesToCaster(effect)) {
                effect->setVictim(first);
                first->addEffect(effect);
            } else if (second) {
                effect->setVictim(second);
                second->addEffect(effect);
            } else {
                vstd::logger::warning("Skipping opponent-target effect without target:", this->to_string());
            }
        }
    }
}

int CInteraction::getManaCost() const { return manaCost; }

void CInteraction::setManaCost(int value) { manaCost = value; }

bool CInteraction::getSelfTarget() const { return selfTarget; }

void CInteraction::setSelfTarget(bool value) { selfTarget = value; }

bool CInteraction::effectRoutesToCaster(const std::shared_ptr<CEffect> &effect) const {
    // An explicit selfTarget always routes the effect to the caster, regardless of
    // tags. Otherwise, preserve the legacy behavior where a Buff-tagged effect is a
    // self-buff (compatibility fallback for configs authored before selfTarget); every
    // other effect routes to the opponent.
    if (selfTarget) {
        return true;
    }
    return effect && effect->hasTag(CTag::Buff);
}

std::shared_ptr<CEffect> CInteraction::getEffect() const { return effect; }

void CInteraction::setEffect(const std::shared_ptr<CEffect> value) { effect = value; }

void CInteraction::performAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "performAction"); !override.is_none()) {
        PY_SAFE(override(first, second); return;)
    }
}

bool CInteraction::configureEffect(std::shared_ptr<CEffect> effect) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "configureEffect"); !override.is_none()) {
        PY_SAFE_RET_VAL(return override(effect).cast<bool>();, true)
    }
    return true;
}
