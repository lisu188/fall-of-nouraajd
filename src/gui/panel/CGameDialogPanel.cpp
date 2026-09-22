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

#include "CGameDialogPanel.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CSceneManager.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"
#include "gui/object/CWidget.h"
#include "object/CDialog.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"

#include <algorithm>
#include <sstream>
#include <vector>

namespace {
constexpr const char *HISTORY_PROPERTY = "uiDialogueHistory";
constexpr std::size_t HISTORY_LIMIT = 80;
constexpr std::size_t HISTORY_BYTES = 32768;

json readHistory(const std::shared_ptr<CPlayer> &player) {
    if (!player) {
        return json::array();
    }
    auto text = player->getStringProperty(HISTORY_PROPERTY);
    try {
        auto entries = json::parse(text.empty() ? "[]" : text);
        return entries.is_array() ? entries : json::array();
    } catch (const std::exception &) {
        return json::array();
    }
}
} // namespace

const std::shared_ptr<CDialog> &CGameDialogPanel::getDialog() const { return dialog; }

void CGameDialogPanel::setDialog(const std::shared_ptr<CDialog> &_dialog) {
    dialog = _dialog;
    currentStateId = "ENTRY";
    recordedStateId.clear();
    bodyScroll = 0;
    choiceStart = 0;
    focusedChoice = -1;
    readingHistory = false;
    readingObjective = false;
}

void CGameDialogPanel::appendHistory(const std::string &speaker, const std::string &text, const std::string &kind) {
    auto game = getGame();
    auto map = game ? game->getMap() : nullptr;
    auto player = map ? map->getPlayer() : nullptr;
    if (!player || text.empty()) {
        return;
    }
    auto entries = readHistory(player);
    auto end = std::min<std::size_t>(text.size(), 8192);
    while (end < text.size() && end > 0 && (static_cast<unsigned char>(text[end]) & 0xc0) == 0x80) {
        --end;
    }
    entries[entries.size()] = json({{"speaker", speaker},
                                    {"text", text.substr(0, end)},
                                    {"kind", kind},
                                    {"dialog", dialog ? dialog->getTypeId() : ""},
                                    {"state", currentStateId}});
    std::size_t first = entries.size();
    std::size_t bytes = 2;
    while (first > 0 && entries.size() - first < HISTORY_LIMIT) {
        const auto entryBytes = entries[first - 1].dump().size() + 1;
        if (bytes + entryBytes > HISTORY_BYTES) {
            break;
        }
        bytes += entryBytes;
        --first;
    }
    auto bounded = json::array();
    for (std::size_t index = first; index < entries.size(); ++index) {
        bounded[bounded.size()] = entries[index];
    }
    player->setStringProperty(HISTORY_PROPERTY, bounded.dump());
}

void CGameDialogPanel::loadHistory() {
    historyText.clear();
    auto game = getGame();
    auto map = game ? game->getMap() : nullptr;
    for (const auto &entry : readHistory(map ? map->getPlayer() : nullptr)) {
        if (!entry.is_object() || !entry.contains("text") || !entry["text"].is_string()) {
            continue;
        }
        const auto speaker = entry.contains("speaker") && entry["speaker"].is_string()
                                 ? entry["speaker"].get<std::string>()
                                 : "Conversation";
        historyText.push_back(speaker + "\n" + entry["text"].get<std::string>());
    }
    if (historyText.empty()) {
        historyText.push_back("No conversations recorded yet.");
    }
}

void CGameDialogPanel::toggleHistory() {
    readingObjective = false;
    readingHistory = !readingHistory;
    bodyScroll = 0;
    if (readingHistory) {
        loadHistory();
    }
    reload();
}

std::string CGameDialogPanel::getFooterHint() const {
    if (readingHistory || readingObjective)
        return "Esc Return | Scroll to read";
    return questContext.empty() ? "1-9 Reply | Arrows + Enter | H History"
                                : "1-9 Reply | Arrows + Enter | H History | O Objective";
}

void CGameDialogPanel::reload() {
    auto self = this->ptr<CGameDialogPanel>();
    auto gui = getGui();
    if (!dialog || currentStateId == "EXIT") {
        close();
        return;
    }
    auto state = dialog->getState(currentStateId);
    if (!state) {
        vstd::logger::warning("Closing dialog with missing state:", currentStateId);
        close();
        return;
    }
    if (!gui || !getLayout()) {
        return;
    }
    auto speaker = state->getStringProperty("speaker");
    if (speaker.empty()) {
        speaker = dialog->getStringProperty("speaker");
    }
    if (speaker.empty()) {
        speaker = "Conversation";
    }
    questContext.clear();
    const auto map = getGame()->getMap();
    const auto player = map ? map->getPlayer() : nullptr;
    std::set<std::string> relatedQuestIds;
    std::istringstream identifiers(dialog->getStringProperty("questIds"));
    std::string identifier;
    while (std::getline(identifiers, identifier, ',')) {
        relatedQuestIds.insert(identifier);
    }
    if (player) {
        for (const auto &quest : player->getQuests()) {
            if (!quest || !relatedQuestIds.contains(quest->getTypeId()))
                continue;
            auto objective = quest->getObjective();
            if (objective.empty())
                objective = quest->getDescription();
            if (!objective.empty()) {
                if (!questContext.empty())
                    questContext += "\n";
                questContext += objective;
            }
        }
    }
    if (questContext.empty())
        readingObjective = false;
    const bool reading = readingHistory || readingObjective;
    setTitle(readingHistory ? "Conversation history" : readingObjective ? "Current objective" : speaker);
    bodyText = state->getText();
    if (recordedStateId != currentStateId) {
        appendHistory(speaker, bodyText, "speech");
        recordedStateId = currentStateId;
    }
    const auto rect = getLayout()->getRect(self);
    measuredWidth = rect->w;
    measuredHeight = rect->h;
    measuredScale = gui->getUiScale();
    measuredTextScale = gui->getTextScale();
    const int padding = UiTheme::scaled(gui, 24);
    const int header = getShellHeaderHeight(gui) + UiTheme::scaled(gui, 16);
    const int gap = UiTheme::scaled(gui, 8);
    const int width = std::max(1, rect->w - padding * 2);
    const int footer = std::max(UiTheme::scaled(gui, 56),
                                gui->getTextManager()->measureText(getFooterHint(), width, "caption").second + gap * 2);
    footerRect = CUtil::rect(rect->x + padding, rect->y + rect->h - footer + gap, width, footer - gap * 2);
    const int available = std::max(1, rect->h - header - footer);
    const int contextHeight =
        reading || questContext.empty()
            ? 0
            : std::min(available / 3,
                       gui->getTextManager()->measureText("Current objective\n" + questContext, width).second + gap);
    const int bodyHeight = reading ? available : std::max(1, (available - contextHeight) * 42 / 100);
    bodyRect = CUtil::rect(rect->x + padding, rect->y + header, width, bodyHeight);
    questRect = contextHeight > 0
                    ? CUtil::rect(rect->x + padding, rect->y + header + bodyHeight + gap, width, contextHeight)
                    : nullptr;
    paragraphs.clear();
    int contentHeight = 0;
    const int lineHeight = std::max(1, gui->getTextManager()->measureText("Ag", width).second);
    const auto texts =
        readingHistory ? historyText : std::vector<std::string>{readingObjective ? questContext : bodyText};
    for (const auto &text : texts) {
        std::istringstream lines(text);
        std::string line;
        while (std::getline(lines, line)) {
            std::size_t offset = 0;
            do {
                auto end = std::min(offset + 1024, line.size());
                while (end < line.size() && end > offset && (static_cast<unsigned char>(line[end]) & 0xc0) == 0x80) {
                    --end;
                }
                const auto chunk = line.substr(offset, end - offset);
                const int height = std::max(lineHeight, gui->getTextManager()->measureText(chunk, width).second);
                paragraphs.push_back({chunk, contentHeight, height});
                contentHeight += height;
                offset = end;
            } while (offset < line.size());
        }
        if (readingHistory)
            contentHeight += UiTheme::scaled(gui, 20);
    }
    bodyMaximum = std::max(0, contentHeight - bodyHeight);
    bodyScroll = std::clamp(bodyScroll, 0, bodyMaximum);

    std::set<std::shared_ptr<CGameGraphicsObject>> widgets;
    if (!reading) {
        auto options = getCurrentOptions();
        choiceStart = std::clamp(choiceStart, 0, std::max(0, static_cast<int>(options.size()) - 1));
        choiceEnd = choiceStart;
        int y = header + bodyHeight + contextHeight + gap * 2;
        const int bottom = rect->h - footer;
        for (const auto &[index, option] : options) {
            if (index < choiceStart) {
                continue;
            }
            const auto actionLabel = option->getStringProperty("actionLabel");
            auto text = std::to_string(index + 1) + "  ";
            if (!actionLabel.empty()) {
                text += actionLabel + "\n";
            }
            text += option->getText();
            const int height = std::max(UiTheme::scaled(gui, 44),
                                        gui->getTextManager()->measureText(text, width - padding).second + gap * 2);
            if (y + height > bottom && index > choiceStart) {
                break;
            }
            std::string clickName = "chooseReply" + std::to_string(index);
            self->meta()->set_method<CGameGraphicsObject, void, std::shared_ptr<CGui>>(
                clickName, self, [option](CGameGraphicsObject *panel, std::shared_ptr<CGui>) {
                    static_cast<CGameDialogPanel *>(panel)->selectOption(option);
                });
            auto widget = getGame()->createObject<CButton>("CButton");
            widget->setClick(clickName);
            widget->setText(text);
            widget->setCentered(false);
            widget->setBoolProperty("selected", focusedChoice == index);
            auto layout = getGame()->createObject<CLayout>("CLayout");
            layout->setX(std::to_string(padding));
            layout->setY(std::to_string(y));
            layout->setW(std::to_string(width));
            layout->setH(std::to_string(std::max(1, std::min(height, bottom - y))));
            widget->setLayout(layout);
            widgets.insert(widget);
            choiceEnd = index + 1;
            y += height + gap;
        }
    }
    setChildren(widgets);
}

void CGameDialogPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int) {
    if (!gui || !rect) {
        return;
    }
    if (!bodyRect || measuredWidth != rect->w || measuredHeight != rect->h || measuredScale != gui->getUiScale() ||
        measuredTextScale != gui->getTextScale()) {
        reload();
    }
    if (!bodyRect) {
        return;
    }
    // Panels can move without changing size. Keep the reading viewport attached to the panel.
    bodyRect->x = rect->x + UiTheme::scaled(gui, 24);
    bodyRect->y = rect->y + getShellHeaderHeight(gui) + UiTheme::scaled(gui, 16);
    auto textManager = gui->getTextManager();
    if (questRect) {
        questRect->x = bodyRect->x;
        questRect->y = bodyRect->y + bodyRect->h + UiTheme::scaled(gui, 8);
        textManager->drawTextStyled("Current objective\n" + questContext, questRect, "body", UiTheme::Muted);
    }
    for (const auto &paragraph : paragraphs) {
        if (paragraph.y + paragraph.height > bodyScroll && paragraph.y < bodyScroll + bodyRect->h) {
            textManager->drawTextStyled(paragraph.text, bodyRect, "body", UiTheme::Text, false,
                                        paragraph.y - bodyScroll);
        }
    }
    if (footerRect) {
        footerRect->x = bodyRect->x;
        footerRect->y = rect->y + rect->h - footerRect->h - UiTheme::scaled(gui, 8);
        textManager->drawTextStyled(getFooterHint(), footerRect, "caption", UiTheme::Muted);
    }
}

std::shared_ptr<CDialogOption> CGameDialogPanel::getOption(int option) {
    auto options = getCurrentOptions();
    auto found = options.find(option);
    return found == options.end() ? nullptr : found->second;
}

std::map<int, std::shared_ptr<CDialogOption>> CGameDialogPanel::getCurrentOptions() {
    struct OptionComparator {
        bool operator()(const std::shared_ptr<CDialogOption> &a, const std::shared_ptr<CDialogOption> &b) const {
            return a->getNumber() < b->getNumber();
        }
    };
    std::set<std::shared_ptr<CDialogOption>, OptionComparator> options;
    if (!dialog) {
        return {};
    }
    auto state = dialog->getState(currentStateId);
    if (!state) {
        return {};
    }
    for (const auto &option : state->getOptions()) {
        if (option && (option->getCondition().empty() || dialog->invokeCondition(option->getCondition()))) {
            options.insert(option);
        }
    }
    std::map<int, std::shared_ptr<CDialogOption>> result;
    int index = 0;
    for (const auto &option : options) {
        result[index++] = option;
    }
    return result;
}

void CGameDialogPanel::selectOption(int option) { selectOption(getOption(option)); }

void CGameDialogPanel::selectOption(const std::shared_ptr<CDialogOption> &option) {
    if (!option || !dialog || readingHistory || readingObjective || !getGui()) {
        return;
    }
    // Conditions may have changed since the reply was laid out.
    if (!option->getCondition().empty() && !dialog->invokeCondition(option->getCondition())) {
        reload();
        return;
    }
    if (CPlaytestTrace::enabled()) {
        json fields = {{"action", option->getAction()},
                       {"dialog", CPlaytestTrace::objectRef(dialog)},
                       {"nextStateId", option->getNextStateId()},
                       {"optionNumber", option->getNumber()},
                       {"stateId", currentStateId}};
        CPlaytestTrace::addMapContext(fields, getGame() ? getGame()->getMap() : nullptr);
        CPlaytestTrace::record("dialog_option_selected", fields);
    }
    auto game = getGame();
    auto sourceMap = game ? game->getMap() : nullptr;
    appendHistory("You", option->getText(), "reply");
    if (!option->getAction().empty() && !dialog->invokeActionChecked(option->getAction())) {
        return;
    }
    // An action may complete a chapter or destroy its speaker. Never revive the outgoing panel.
    if (!getGui() || (game && (game->getMap() != sourceMap || game->getSceneManager()->isTransitionPending()))) {
        close();
        return;
    }
    currentStateId = option->getNextStateId().empty() ? "EXIT" : option->getNextStateId();
    const auto afterCondition = option->getStringProperty("afterCondition");
    const auto afterState = option->getStringProperty("afterStateId");
    if (!afterCondition.empty() && !afterState.empty() && dialog->invokeCondition(afterCondition)) {
        currentStateId = afterState;
    }
    recordedStateId.clear();
    bodyScroll = 0;
    choiceStart = 0;
    focusedChoice = -1;
    reload();
}

bool CGameDialogPanel::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (event && event->type == SDL_KEYDOWN && event->key.repeat &&
        (CUtil::parseKey(event->key.keysym.sym) > 0 || event->key.keysym.sym == SDLK_RETURN)) {
        return true;
    }
    return CGamePanel::event(gui, event);
}

bool CGameDialogPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type != SDL_KEYDOWN) {
        return true;
    }
    if (key == SDLK_ESCAPE) {
        if (readingObjective) {
            readingObjective = false;
            bodyScroll = 0;
            reload();
        } else if (readingHistory) {
            toggleHistory();
        } else {
            close();
        }
        return true;
    }
    if (key == SDLK_h) {
        toggleHistory();
        return true;
    }
    if (key == SDLK_o && !questContext.empty()) {
        readingObjective = !readingObjective;
        readingHistory = false;
        bodyScroll = 0;
        reload();
        return true;
    }
    if (key == SDLK_PAGEUP || key == SDLK_PAGEDOWN || key == SDLK_HOME || key == SDLK_END || readingHistory ||
        readingObjective) {
        const int step = bodyRect ? std::max(1, bodyRect->h - UiTheme::scaled(gui, 24)) : 100;
        if (key == SDLK_HOME)
            bodyScroll = 0;
        if (key == SDLK_END)
            bodyScroll = bodyMaximum;
        if (key == SDLK_PAGEUP)
            bodyScroll -= step;
        if (key == SDLK_PAGEDOWN)
            bodyScroll += step;
        if ((readingHistory || readingObjective) && key == SDLK_UP)
            bodyScroll -= UiTheme::scaled(gui, 32);
        if ((readingHistory || readingObjective) && key == SDLK_DOWN)
            bodyScroll += UiTheme::scaled(gui, 32);
        bodyScroll = std::clamp(bodyScroll, 0, bodyMaximum);
        return true;
    }
    auto options = getCurrentOptions();
    if (key == SDLK_UP || key == SDLK_DOWN) {
        if (!options.empty()) {
            focusedChoice =
                std::clamp(focusedChoice + (key == SDLK_DOWN ? 1 : -1), 0, static_cast<int>(options.size()) - 1);
            if (focusedChoice < choiceStart || focusedChoice >= choiceEnd) {
                choiceStart = focusedChoice;
            }
            reload();
        }
    } else if (key == SDLK_RETURN && focusedChoice >= 0) {
        selectOption(focusedChoice);
    } else if (const int index = CUtil::parseKey(key) - 1; index >= 0 && options.contains(index)) {
        selectOption(index);
    }
    return true;
}

bool CGameDialogPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType, int, int y, int, int wheelY) {
    if (readingHistory || readingObjective ||
        y < getShellHeaderHeight(gui) + UiTheme::scaled(gui, 16) + (bodyRect ? bodyRect->h : 0)) {
        bodyScroll = std::clamp(bodyScroll - wheelY * UiTheme::scaled(gui, 64), 0, bodyMaximum);
    } else {
        choiceStart =
            std::clamp(choiceStart - wheelY, 0, std::max(0, static_cast<int>(getCurrentOptions().size()) - 1));
        reload();
    }
    return true;
}

bool CGameDialogPanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (button == SDL_BUTTON_LEFT && getLayout()) {
        auto rect = getLayout()->getRect(this->ptr<CGameGraphicsObject>());
        const bool inObjective = questRect && x >= questRect->x - rect->x &&
                                 x < questRect->x - rect->x + questRect->w && y >= questRect->y - rect->y &&
                                 y < questRect->y - rect->y + questRect->h;
        if (type == SDL_MOUSEBUTTONDOWN) {
            objectivePressed = inObjective;
            if (inObjective)
                return true;
        } else if (type == SDL_MOUSEBUTTONUP) {
            const bool activate = objectivePressed && inObjective;
            objectivePressed = false;
            if (activate)
                return keyboardEvent(gui, SDL_KEYDOWN, SDLK_o);
        }
        const bool inside = footerRect && x >= footerRect->x - rect->x && x < footerRect->x - rect->x + footerRect->w &&
                            y >= footerRect->y - rect->y && y < footerRect->y - rect->y + footerRect->h;
        if (type == SDL_MOUSEBUTTONDOWN) {
            historyPressed = inside;
            if (inside)
                return true;
        } else if (type == SDL_MOUSEBUTTONUP) {
            const bool activate = historyPressed && inside;
            historyPressed = false;
            if (activate) {
                toggleHistory();
                return true;
            }
        }
    }
    return CGamePanel::mouseEvent(gui, type, button, x, y);
}
