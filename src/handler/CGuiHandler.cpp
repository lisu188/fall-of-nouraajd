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
#include "CGuiHandler.h"
#include "core/CGame.h"
#include "core/CList.h"
#include "core/CMap.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CTooltip.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameLootPanel.h"
#include "gui/panel/CGameQuestionPanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "object/CDialog.h"
#include "object/CMarket.h"

CGuiHandler::CGuiHandler() {}

void CGuiHandler::showMessage(std::string message) {
  std::shared_ptr<CGameTextPanel> panel =
      _game.lock()->createObject<CGameTextPanel>("textPanel");
  panel->setText(message);
  _game.lock()->getGui()->pushChild(panel);
  panel->awaitClosing();
}

void CGuiHandler::showInfo(std::string message, bool centered) {
  std::shared_ptr<CGameTextPanel> panel =
      _game.lock()->createObject<CGameTextPanel>("infoPanel");
  panel->setText(message);
  panel->setCentered(centered);
  _game.lock()->getGui()->pushChild(panel);
  panel->awaitClosing();
}

bool CGuiHandler::showQuestion(std::string question) {
  std::shared_ptr<CGameQuestionPanel> panel =
      _game.lock()->createObject<CGameQuestionPanel>("questionPanel");
  panel->setQuestion(question);
  _game.lock()->getGui()->pushChild(panel);
  return panel->awaitAnswer();
}

void CGuiHandler::showTrade(std::shared_ptr<CMarket> market) {
  std::shared_ptr<CGameTradePanel> panel =
      _game.lock()->createObject<CGameTradePanel>("tradePanel");
  panel->setMarket(market);
  _game.lock()->getGui()->pushChild(panel);
  panel->awaitClosing();
}

void CGuiHandler::showDialog(std::shared_ptr<CDialog> dialog) {
  std::shared_ptr<CGameDialogPanel> panel =
      _game.lock()->createObject<CGameDialogPanel>("dialogPanel");
  panel->setDialog(dialog);
  panel->reload();
  _game.lock()->getGui()->pushChild(panel);
  panel->awaitClosing();
}

void CGuiHandler::showLoot(std::shared_ptr<CCreature> creature,
                           std::set<std::shared_ptr<CItem>> items) {
  std::shared_ptr<CGameLootPanel> panel =
      _game.lock()->createObject<CGameLootPanel>("lootPanel");
  panel->setCreature(creature);
  panel->setItems(items);
  _game.lock()->getGui()->pushChild(panel);
  panel->awaitClosing();
}

CGuiHandler::CGuiHandler(std::shared_ptr<CGame> game) : _game(game) {}

std::string CGuiHandler::showSelection(std::shared_ptr<CListString> list) {
  std::shared_ptr<CGamePanel> panel =
      _game.lock()->createObject<CGamePanel>("selectionPanel");
  vstd::cast<CCenteredLayout>(panel->getLayout())
      ->setH(vstd::str(75 * list->getValues().size()));

  std::shared_ptr<std::string> selected;

  std::set<std::shared_ptr<CGameGraphicsObject>> widgets;
  int i = 0;
  // TODO: unify with CGameDialogPanel
  for (auto item : list->getValues()) {
    std::string clickName = vstd::str("click") + vstd::str(i);

    panel->meta()->set_method<CGameGraphicsObject, void, std::shared_ptr<CGui>>(
        clickName, panel,
        [item, &selected](CGameGraphicsObject *self,
                          std::shared_ptr<CGui> gui) {
          selected = std::make_shared<std::string>(item);
        });

    std::shared_ptr<CButton> widget =
        _game.lock()->createObject<CButton>("CButton");
    widget->setClick(clickName);
    widget->setText(item);

    std::shared_ptr<CLayout> layout =
        _game.lock()->createObject<CLayout>("CLayout");
    int percentSize = 100.0 / list->getValues().size();
    layout->setX(vstd::str(0) + "%");
    layout->setY(vstd::str(percentSize * i) + "%");
    layout->setW(vstd::str(100) + "%");
    layout->setH(vstd::str(percentSize) + "%");
    widget->setLayout(layout);
    widgets.insert(widget);
    i++;
  }

  panel->setChildren(widgets);

  _game.lock()->getGui()->pushChild(panel);

  vstd::wait_until([&]() { return selected != nullptr; });

  panel->close();

  return *selected;
}

void CGuiHandler::showTooltip(std::string text, int x, int y) {
  if (text.length() > 0) {
    auto layout = _game.lock()->createObject<CLayout>();

    auto textureSize =
        _game.lock()->getGui()->getTextManager()->getTextureSize(text);

    int width = vstd::percent(textureSize.first, 125);
    int height = vstd::percent(textureSize.second, 125);

    layout->setW(vstd::str(width));  // TODO: layout should accept functions;
    layout->setH(vstd::str(height)); // TODO: layout should accept functions;

    layout->setX(vstd::str(x - width / 2));  // TODO: extract to util
    layout->setY(vstd::str(y - height / 2)); // TODO: extract to util

    auto tooltip = _game.lock()->createObject<CTooltip>();
    tooltip->setText(text);
    tooltip->setLayout(layout);
    _game.lock()->getGui()->pushChild(tooltip);
  }
}

void CGuiHandler::flipPanel(std::string panel, std::string hotkey) {
  std::shared_ptr<CGame> game = _game.lock();
  auto panelClas = game->getObjectHandler()->getClass(panel);
  if (auto currentPanel =
          vstd::cast<CGamePanel>(game->getGui()->findChild(panelClas))) {
    currentPanel->close();
  } else {
    std::shared_ptr<CGamePanel> child = game->createObject<CGamePanel>(panel);
    game->getGui()->pushChild(child);

    auto keyPred = [hotkey](std::shared_ptr<CGui> gui,
                            std::shared_ptr<CGameGraphicsObject> self,
                            SDL_Event *event) {
      return event->type == SDL_KEYDOWN && event->key.keysym.sym == hotkey[0];
    };
    auto _self = this->ptr<CGuiHandler>();
    child->registerEventCallback(
        keyPred,
        [_self, panel, hotkey](std::shared_ptr<CGui> gui,
                               std::shared_ptr<CGameGraphicsObject> self,
                               SDL_Event *event) {
          _self->flipPanel(panel, hotkey);
          return true;
        });

    child->awaitClosing();
  }
}
