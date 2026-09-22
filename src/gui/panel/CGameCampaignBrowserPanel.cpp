/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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
#include "CGameCampaignBrowserPanel.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"
#include "gui/CUiArtwork.h"

#include <algorithm>
#include <sstream>
#include <stdexcept>

namespace {
constexpr int CONFIRM_TARGET = 2'000'000;
constexpr int BACK_TARGET = 2'000'001;
constexpr int RACE_TARGET = 1'000'000;
constexpr int PAGE_TARGET = 3'000'000;

bool containsPoint(const SDL_Rect &rect, int x, int y) {
    return x >= rect.x && y >= rect.y && x < rect.x + rect.w && y < rect.y + rect.h;
}
} // namespace

std::vector<CGameCampaignBrowserPanel::ChoiceOption>
CGameCampaignBrowserPanel::parseChoices(const std::string &choicesJson) {
    auto document = json::parse(choicesJson);
    if (!document.is_array()) {
        throw std::invalid_argument("Choice options must be an ordered array.");
    }
    std::set<std::string> ids;
    std::vector<ChoiceOption> result;
    for (const auto &entry : document) {
        if (!entry.is_object() || !entry.contains("id") || !entry["id"].is_string() || !entry.contains("label") ||
            !entry["label"].is_string() || (entry.contains("detail") && !entry["detail"].is_string()) ||
            (entry.contains("enabled") && !entry["enabled"].is_boolean()) ||
            (entry.contains("image") && !entry["image"].is_string())) {
            throw std::invalid_argument("Every choice requires a string id and label.");
        }
        ChoiceOption option{entry["id"].get<std::string>(), entry["label"].get<std::string>(),
                            entry.value("detail", std::string()), entry.value("enabled", true)};
        if (option.id.empty() || !ids.insert(option.id).second) {
            throw std::invalid_argument("Choice ids must be nonempty and unique.");
        }
        option.image = entry.value("image", std::string());
        if (!option.image.empty() && !UiArtwork::validPath(option.image))
            throw std::invalid_argument("Choice artwork must name an image resource.");
        if (entry.contains("previews") && entry["previews"].is_object()) {
            for (const auto &[id, preview] : entry["previews"].items()) {
                if (preview.is_string())
                    option.previews[id] = preview.get<std::string>();
            }
        }
        result.push_back(std::move(option));
    }
    return result;
}

void CGameCampaignBrowserPanel::configureChoices(std::string titleValue, std::vector<ChoiceOption> values,
                                                 std::string action, std::string back) {
    title = std::move(titleValue);
    setTitle(title);
    options = std::move(values);
    actionLabel = std::move(action);
    backLabel = std::move(back);
    managedChoices = true;
    characterChoices = false;
    textInputMode = false;
    choice.reset();
    selectedIndex = -1;
    selectedRaceIndex = -1;
    activeColumn = 0;
    activePage = 0;
    pressedTarget = hoveredTarget = -1;
    selectedId.clear();
    detailImage.clear();
    races.clear();
    listOffset = raceOffset = detailOffset = 0;
    measuredLabelWidth = 0;
    detailMeasuredWidth = 0;
    setChildren({});
    if (!options.empty()) {
        selectIndex(0, 0);
    } else {
        detailText = "No choices are available. Use Back to return.";
    }
}

void CGameCampaignBrowserPanel::configureTextInput(std::string titleValue, std::string prompt,
                                                   std::string initialValue) {
    configureChoices(std::move(titleValue), {}, "Save", "Back");
    textInputMode = true;
    inputText = std::move(initialValue);
    inputPrompt = std::move(prompt);
    inputSelectAll = true;
}

std::string CGameCampaignBrowserPanel::getInputText() const { return inputText; }

bool CGameCampaignBrowserPanel::isCompactLayout() const { return compactLayout; }

int CGameCampaignBrowserPanel::getActivePage() const { return activePage; }

void CGameCampaignBrowserPanel::selectPage(int page) {
    activePage = std::clamp(page, 0, characterChoices ? 2 : 1);
    if (activePage < (characterChoices ? 2 : 1))
        activeColumn = activePage;
}

void CGameCampaignBrowserPanel::appendInput(const std::string &text) {
    if (!textInputMode || text.empty() || (inputSelectAll ? 0 : inputText.size()) + text.size() > 80 ||
        std::any_of(text.begin(), text.end(), [](unsigned char value) { return value < 32 || value == 127; })) {
        return;
    }
    if (inputSelectAll) {
        inputText.clear();
        inputSelectAll = false;
    }
    inputText += text;
}

bool CGameCampaignBrowserPanel::event(std::shared_ptr<CGui> gui, SDL_Event *inputEvent) {
    if (textInputMode && inputEvent && inputEvent->type == SDL_TEXTINPUT && isAttachedToGui(gui) && isVisible()) {
        appendInput(inputEvent->text.text);
        return true;
    }
    return CGamePanel::event(gui, inputEvent);
}

void CGameCampaignBrowserPanel::configureCharacterChoices(std::vector<ChoiceOption> classes,
                                                          std::vector<ChoiceOption> raceValues,
                                                          std::pair<std::string, std::string> previous) {
    configureChoices("Create your character", std::move(classes), "Begin adventure", "Back");
    characterChoices = true;
    races = std::move(raceValues);
    activeColumn = 0;
    if (!races.empty()) {
        selectIndex(0, 1);
    }
    for (int index = 0; index < static_cast<int>(options.size()); ++index)
        if (options[index].id == previous.first)
            selectIndex(index, 0);
    for (int index = 0; index < static_cast<int>(races.size()); ++index)
        if (races[index].id == previous.second)
            selectIndex(index, 1);
    updateDetail();
}

std::pair<std::string, std::string> CGameCampaignBrowserPanel::getPreviewedCharacter() const {
    return {selectedId, selectedRaceIndex >= 0 ? races[selectedRaceIndex].id : ""};
}

std::pair<std::string, std::string> CGameCampaignBrowserPanel::awaitCharacterChoice() {
    const auto selected = awaitChoice();
    if (selected.empty() || selectedRaceIndex < 0) {
        return {"", ""};
    }
    return {selected, races[selectedRaceIndex].id};
}

bool CGameCampaignBrowserPanel::canConfirm() const {
    if (textInputMode) {
        return !inputText.empty();
    }
    if (!managedChoices) {
        return !selectedId.empty();
    }
    return selectedIndex >= 0 && options[selectedIndex].enabled &&
           (!characterChoices || (selectedRaceIndex >= 0 && races[selectedRaceIndex].enabled));
}

void CGameCampaignBrowserPanel::selectIndex(int index, int column) {
    auto &values = column == 1 ? races : options;
    if (index < 0 || index >= static_cast<int>(values.size())) {
        return;
    }
    (column == 1 ? selectedRaceIndex : selectedIndex) = index;
    auto &offset = column == 1 ? raceOffset : listOffset;
    const int rows = std::max(1, listRect(column).h / rowHeight);
    if (index < offset) {
        offset = index;
    } else if (index >= offset + rows) {
        offset = index - rows + 1;
    }
    if (column == 0) {
        selectedId = values[index].id;
    }
    detailOffset = 0;
    updateDetail();
}

void CGameCampaignBrowserPanel::moveSelection(int delta) {
    const auto &values = activeColumn == 1 ? races : options;
    if (values.empty()) {
        return;
    }
    const int index = activeColumn == 1 ? selectedRaceIndex : selectedIndex;
    selectIndex(std::clamp(index + delta, 0, static_cast<int>(values.size()) - 1), activeColumn);
}

void CGameCampaignBrowserPanel::updateDetail() {
    detailMeasuredWidth = 0;
    if (selectedIndex < 0) {
        return;
    }
    const auto &selected = options[selectedIndex];
    detailImage = selected.image;
    detailText = selected.label + "\n\n" + selected.detail;
    if (!selected.enabled) {
        detailText += "\n\nUnavailable";
    }
    if (characterChoices && selectedRaceIndex >= 0) {
        const auto &race = races[selectedRaceIndex];
        if (selected.previews.contains(race.id)) {
            detailText = selected.label + " / " + race.label + "\n\n" + selected.previews.at(race.id);
        } else {
            detailText += "\n\n" + race.label + "\n" + race.detail;
        }
        detailText += "\n\nReview your class and race, then choose Begin adventure.";
    }
}

SDL_Rect CGameCampaignBrowserPanel::listRect(int column) const {
    const int margin = std::max(16, panelWidth / 40);
    const int top = headerHeight;
    const int bottom = footerHeight;
    int available = std::max(rowHeight, panelHeight - top - bottom);
    const auto &values = column == 1 ? races : options;
    if (static_cast<int>(values.size()) > std::max(1, available / rowHeight))
        available = std::max(rowHeight, available - hintHeight - 8);
    if (compactLayout)
        return {margin, top, panelWidth - margin * 2, available};
    const int width = characterChoices ? panelWidth * 22 / 100 : panelWidth * 38 / 100;
    return {margin + column * (width + margin / 2), top, width, available};
}

SDL_Rect CGameCampaignBrowserPanel::detailRect() const {
    auto list = listRect(characterChoices ? 1 : 0);
    list.h = std::max(rowHeight, panelHeight - headerHeight - footerHeight);
    if (compactLayout)
        return list;
    const int margin = std::max(16, panelWidth / 40);
    const int left = list.x + list.w + margin;
    return {left, list.y, std::max(1, panelWidth - left - margin), list.h};
}

SDL_Rect CGameCampaignBrowserPanel::getDetailViewport() const { return detailRect(); }

SDL_Rect CGameCampaignBrowserPanel::getChoiceViewport(int column) const { return listRect(column); }

SDL_Rect CGameCampaignBrowserPanel::getConfirmationBounds() const { return actionRect(); }

int CGameCampaignBrowserPanel::getDetailScrollOffset() const { return detailOffset; }

SDL_Rect CGameCampaignBrowserPanel::actionRect() const {
    return {panelWidth * 59 / 100, panelHeight - buttonHeight - hintHeight - 24, panelWidth * 37 / 100, buttonHeight};
}

SDL_Rect CGameCampaignBrowserPanel::backRect() const {
    return {panelWidth * 4 / 100, panelHeight - buttonHeight - hintHeight - 24, panelWidth * 25 / 100, buttonHeight};
}

SDL_Rect CGameCampaignBrowserPanel::pageRect(int page) const {
    const int margin = std::max(16, panelWidth / 40);
    const int count = characterChoices ? 3 : 2;
    const int width = (panelWidth - margin * 2) / count;
    return {margin + page * width, headerHeight - hintHeight - 16, width - 8, hintHeight + 8};
}

int CGameCampaignBrowserPanel::hitTarget(int x, int y) const {
    if (compactLayout) {
        for (int page = 0; page <= (characterChoices ? 2 : 1); ++page)
            if (containsPoint(pageRect(page), x, y))
                return PAGE_TARGET + page;
    }
    if (containsPoint(actionRect(), x, y)) {
        return CONFIRM_TARGET;
    }
    if (containsPoint(backRect(), x, y)) {
        return BACK_TARGET;
    }
    for (int column = 0; !textInputMode && column <= (characterChoices ? 1 : 0); ++column) {
        if (compactLayout && activePage != column)
            continue;
        const auto rect = listRect(column);
        if (containsPoint(rect, x, y)) {
            const int row = (y - rect.y) / rowHeight;
            if (row >= std::max(1, rect.h / rowHeight)) {
                return -1;
            }
            const int index = (column == 1 ? raceOffset : listOffset) + row;
            const auto &values = column == 1 ? races : options;
            if (index < static_cast<int>(values.size())) {
                return index + (column == 1 ? RACE_TARGET : 0);
            }
        }
    }
    return -1;
}

void CGameCampaignBrowserPanel::scrollDetail(int delta) {
    detailOffset = std::clamp(detailOffset + delta, 0, std::max(0, detailHeight - detailRect().h));
}

void CGameCampaignBrowserPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    CGamePanel::renderObject(gui, rect, frameTime);
    if (!managedChoices) {
        return;
    }
    panelWidth = rect->w;
    panelHeight = rect->h;
    const int bodyLine = gui->getTextManager()->measureText("Ag", panelWidth, "body").second;
    hintHeight = gui->getTextManager()->measureText("Ag", panelWidth, "small").second + 4;
    const int actionTextHeight =
        gui->getTextManager()->measureText(actionLabel, panelWidth * 37 / 100 - 24, "body").second;
    const int backTextHeight = gui->getTextManager()->measureText(backLabel, panelWidth * 25 / 100 - 24, "body").second;
    buttonHeight = std::max(48, std::max(actionTextHeight, backTextHeight) + 24);
    compactLayout = !textInputMode && panelWidth < static_cast<int>(1200 * gui->getTextScale());
    headerHeight = getShellHeaderHeight(gui) + (characterChoices && !compactLayout ? hintHeight : 0) + 16;
    footerHeight = buttonHeight + hintHeight + 40;
    const int labelWidth = compactLayout      ? panelWidth - std::max(16, panelWidth / 40) * 2
                           : characterChoices ? panelWidth * 22 / 100
                                              : panelWidth * 38 / 100;
    if (measuredLabelWidth != labelWidth || measuredLabelLine != bodyLine) {
        int labelHeight = bodyLine;
        for (const auto *values : {&options, &races})
            for (const auto &option : *values)
                labelHeight =
                    std::max(labelHeight,
                             gui->getTextManager()->measureText("> " + option.label, labelWidth - 20, "body").second);
        rowHeight = std::max(44, labelHeight + 16);
        measuredLabelWidth = labelWidth;
        measuredLabelLine = bodyLine;
    }
    if (compactLayout)
        headerHeight += hintHeight + 12;
    auto absolute = [&](SDL_Rect value) {
        value.x += rect->x;
        value.y += rect->y;
        return std::make_shared<SDL_Rect>(value);
    };
    auto fill = [&](const SDL_Rect &local, SDL_Color color) {
        auto target = absolute(local);
        UiTheme::fill(gui->getRenderer(), *target, color);
    };
    if (compactLayout) {
        for (int page = 0; page <= (characterChoices ? 2 : 1); ++page) {
            auto target = pageRect(page);
            fill(target, page == activePage ? UiTheme::Selection : UiTheme::Background);
            UiTheme::stroke(gui->getRenderer(), *absolute(target),
                            page == activePage ? UiTheme::Accent : UiTheme::Border);
            const auto label = characterChoices ? (page == 0   ? "Class"
                                                   : page == 1 ? "Race"
                                                               : "Preview")
                                                : (page == 0 ? "Choices" : "Details");
            gui->getTextManager()->drawTextStyled(label, absolute(target), "small", UiTheme::Text, true);
        }
    }
    for (int column = 0; !textInputMode && column <= (characterChoices ? 1 : 0); ++column) {
        if (compactLayout && activePage != column)
            continue;
        const auto bounds = listRect(column);
        const auto &values = column == 1 ? races : options;
        auto &offset = column == 1 ? raceOffset : listOffset;
        const int selected = column == 1 ? selectedRaceIndex : selectedIndex;
        const int visibleRows = std::max(1, bounds.h / rowHeight);
        offset = std::clamp(offset, 0, std::max(0, static_cast<int>(values.size()) - visibleRows));
        if (characterChoices && !compactLayout) {
            gui->getTextManager()->drawTextStyled(column == 0 ? "CLASS" : "RACE",
                                                  absolute({bounds.x, bounds.y - hintHeight - 4, bounds.w, hintHeight}),
                                                  "small", activeColumn == column ? UiTheme::Accent : UiTheme::Muted);
        }
        for (int row = 0; row < visibleRows && offset + row < static_cast<int>(values.size()); ++row) {
            const int index = offset + row;
            const auto &option = values[index];
            SDL_Rect rowRect{bounds.x, bounds.y + row * rowHeight, bounds.w, rowHeight - 6};
            const int target = index + (column == 1 ? RACE_TARGET : 0);
            fill(rowRect, !option.enabled                                ? UiTheme::Background
                          : index == selected || target == hoveredTarget ? UiTheme::Selection
                                                                         : UiTheme::Panel);
            if (index == selected) {
                UiTheme::stroke(gui->getRenderer(), *absolute(rowRect),
                                activeColumn == column ? UiTheme::Accent : UiTheme::Border);
            }
            const std::string marker = index == selected ? "> " : "  ";
            gui->getTextManager()->drawTextStyled(
                marker + option.label, absolute({rowRect.x + 10, rowRect.y + 7, rowRect.w - 20, rowRect.h - 14}),
                "body", option.enabled ? UiTheme::Text : UiTheme::Muted);
        }
        if (static_cast<int>(values.size()) > visibleRows) {
            const auto range = std::to_string(offset + 1) + "-" +
                               std::to_string(std::min(offset + visibleRows, static_cast<int>(values.size()))) + " / " +
                               std::to_string(values.size());
            gui->getTextManager()->drawTextStyled(
                range, absolute({bounds.x, bounds.y + bounds.h + 4, bounds.w, hintHeight}), "small", UiTheme::Muted);
        }
    }
    if (textInputMode) {
        SDL_Rect inputRect{panelWidth / 25, headerHeight, panelWidth * 23 / 25, buttonHeight + 16};
        fill(inputRect, inputSelectAll ? UiTheme::Selection : UiTheme::Background);
        UiTheme::stroke(gui->getRenderer(), *absolute(inputRect), UiTheme::Accent);
        std::string visibleInput = inputText + "|";
        while (visibleInput.size() > 1 &&
               gui->getTextManager()->measureText(visibleInput, 0, "body").first > inputRect.w - 32) {
            visibleInput.erase(0, 1);
            while (!visibleInput.empty() && (static_cast<unsigned char>(visibleInput[0]) & 0xc0) == 0x80) {
                visibleInput.erase(0, 1);
            }
        }
        gui->getTextManager()->drawTextStyled(
            visibleInput, absolute({inputRect.x + 16, inputRect.y + 16, inputRect.w - 32, inputRect.h - 32}), "body",
            UiTheme::Text);
        gui->getTextManager()->drawTextStyled(
            inputPrompt,
            absolute({inputRect.x, inputRect.y + inputRect.h + 24, inputRect.w,
                      std::max(1, panelHeight - footerHeight - inputRect.y - inputRect.h - 24)}),
            "body", UiTheme::Muted);
    } else if (!compactLayout || activePage == (characterChoices ? 2 : 1)) {
        const auto detail = absolute(detailRect());
        renderDetail(gui, detail, frameTime);
        if (detailHeight > detail->h) {
            SDL_Rect track{detail->x + detail->w - 4, detail->y, 4, detail->h};
            UiTheme::fill(gui->getRenderer(), track, UiTheme::Border);
            const int thumbHeight = std::max(16, detail->h * detail->h / detailHeight);
            track.y += detailOffset * (detail->h - thumbHeight) / std::max(1, detailHeight - detail->h);
            track.h = thumbHeight;
            UiTheme::fill(gui->getRenderer(), track, UiTheme::Accent);
        }
    }
    fill(backRect(), UiTheme::Panel);
    fill(actionRect(), canConfirm() ? UiTheme::Selection : UiTheme::Background);
    UiTheme::stroke(gui->getRenderer(), *absolute(backRect()),
                    hoveredTarget == BACK_TARGET ? UiTheme::Accent : UiTheme::Border);
    UiTheme::stroke(gui->getRenderer(), *absolute(actionRect()), canConfirm() ? UiTheme::Accent : UiTheme::Border);
    gui->getTextManager()->drawTextStyled(backLabel, absolute(backRect()), "body", UiTheme::Text, true);
    gui->getTextManager()->drawTextStyled(actionLabel, absolute(actionRect()), "body",
                                          canConfirm() ? UiTheme::Text : UiTheme::Muted, true);
    gui->getTextManager()->drawTextStyled(compactLayout      ? "Tab: next page  |  Enter: confirm  |  Esc: back"
                                          : characterChoices ? "Tab: class/race  |  Enter: begin  |  Esc: back"
                                                             : "Enter: confirm  |  Esc: back",
                                          absolute({20, panelHeight - hintHeight - 10, panelWidth - 40, hintHeight}),
                                          "small", UiTheme::Muted, true);
}

std::string CGameCampaignBrowserPanel::awaitChoice() {
    vstd::wait_until([this]() { return choice != nullptr || !getGui(); });
    return choice ? *choice : "";
}

bool CGameCampaignBrowserPanel::hasChoice() { return choice != nullptr; }

std::string CGameCampaignBrowserPanel::getSelectedId() { return selectedId; }

void CGameCampaignBrowserPanel::setSelectedId(std::string value) { selectedId = value; }

std::string CGameCampaignBrowserPanel::getDetailText() { return detailText; }

std::string CGameCampaignBrowserPanel::getVisibleDetailText() const {
    std::string visible;
    for (const auto &paragraph : detailParagraphs)
        if (paragraph.y + paragraph.height > detailOffset && paragraph.y < detailOffset + detailRect().h)
            visible += paragraph.text + "\n";
    return visible;
}

void CGameCampaignBrowserPanel::setDetailText(std::string value) {
    detailText = std::move(value);
    detailMeasuredWidth = 0;
    detailOffset = 0;
}

void CGameCampaignBrowserPanel::renderDetail(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (!gui || !rect || rect->w <= 0 || rect->h <= 0)
        return;
    auto image = UiArtwork::texture(gui, detailImage);
    const auto artwork = UiArtwork::layout(gui, image, *rect, compactLayout);
    artworkBounds = artwork.image;
    textBounds = artwork.text;
    auto textRect = std::make_shared<SDL_Rect>(textBounds);
    if (detailMeasuredWidth != textRect->w || detailMeasuredTextScale != gui->getTextScale() ||
        detailMeasuredInset != artwork.inset) {
        detailParagraphs.clear();
        detailHeight = artwork.inset;
        const int lineHeight = gui->getTextManager()->measureText("Ag", textRect->w, "body").second;
        std::istringstream lines(detailText);
        std::string line;
        while (std::getline(lines, line)) {
            if (compactLayout && line.empty())
                continue;
            std::size_t offset = 0;
            do {
                auto end = std::min(offset + 1024, line.size());
                while (end < line.size() && end > offset && (static_cast<unsigned char>(line[end]) & 0xc0) == 0x80)
                    --end;
                const auto part = line.substr(offset, end - offset);
                const int height =
                    std::max(lineHeight, gui->getTextManager()->measureText(part, textRect->w, "body").second);
                detailParagraphs.push_back({part, detailHeight, height});
                detailHeight += height;
                offset = end;
            } while (offset < line.size());
        }
        detailMeasuredWidth = textRect->w;
        detailMeasuredTextScale = gui->getTextScale();
        detailMeasuredInset = artwork.inset;
    }
    detailOffset = std::clamp(detailOffset, 0, std::max(0, detailHeight - rect->h));
    UiArtwork::draw(gui, image, artwork.image, *rect, compactLayout ? detailOffset : 0);
    for (const auto &paragraph : detailParagraphs)
        if (paragraph.y + paragraph.height > detailOffset && paragraph.y < detailOffset + rect->h)
            gui->getTextManager()->drawTextStyled(paragraph.text, textRect, "body", UiTheme::Text, false,
                                                  paragraph.y - detailOffset);
}

void CGameCampaignBrowserPanel::clickSelect(std::shared_ptr<CGui> gui) {
    // Selection begins only after SELECT confirms a highlighted campaign; the
    // button is inert until one is picked from the title column.
    if (!canConfirm()) {
        return;
    }
    choice = std::make_shared<std::string>(textInputMode ? inputText : selectedId);
    close();
}

void CGameCampaignBrowserPanel::clickCancel(std::shared_ptr<CGui> gui) {
    choice = std::make_shared<std::string>("");
    close();
}

bool CGameCampaignBrowserPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN && key == SDLK_ESCAPE) {
        // Escape is a cancel path: it resolves the browser to an empty stable id.
        clickCancel(gui);
    } else if (managedChoices && type == SDL_KEYDOWN) {
        if (key == SDLK_RETURN || key == SDLK_KP_ENTER) {
            clickSelect(gui);
        } else if (textInputMode) {
            if (key == SDLK_BACKSPACE) {
                if (inputSelectAll) {
                    inputText.clear();
                } else if (!inputText.empty()) {
                    do {
                        const auto last = static_cast<unsigned char>(inputText.back());
                        inputText.pop_back();
                        if ((last & 0xc0) != 0x80)
                            break;
                    } while (!inputText.empty());
                }
                inputSelectAll = false;
            } else if (key == SDLK_a && (SDL_GetModState() & KMOD_CTRL)) {
                inputSelectAll = true;
            } else if (key == SDLK_DELETE && inputSelectAll) {
                inputText.clear();
                inputSelectAll = false;
            }
        } else if (compactLayout && (key == SDLK_TAB || key == SDLK_LEFT || key == SDLK_RIGHT)) {
            const int count = characterChoices ? 3 : 2;
            const bool previous = key == SDLK_LEFT || (key == SDLK_TAB && (SDL_GetModState() & KMOD_SHIFT));
            selectPage((activePage + (previous ? count - 1 : 1)) % count);
        } else if (compactLayout && activePage == (characterChoices ? 2 : 1) && (key == SDLK_UP || key == SDLK_DOWN)) {
            scrollDetail((key == SDLK_UP ? -1 : 1) * hintHeight);
        } else if (key == SDLK_UP || key == SDLK_DOWN) {
            moveSelection(key == SDLK_UP ? -1 : 1);
        } else if (key == SDLK_TAB && characterChoices) {
            activeColumn = 1 - activeColumn;
        } else if ((key == SDLK_LEFT || key == SDLK_RIGHT) && characterChoices) {
            activeColumn = key == SDLK_LEFT ? 0 : 1;
        } else if (key == SDLK_PAGEUP || key == SDLK_PAGEDOWN) {
            scrollDetail((key == SDLK_PAGEUP ? -1 : 1) * std::max(40, detailRect().h - 40));
        } else if (compactLayout && activePage == (characterChoices ? 2 : 1) && (key == SDLK_HOME || key == SDLK_END)) {
            scrollDetail(key == SDLK_HOME ? -detailHeight : detailHeight);
        } else if (key == SDLK_HOME) {
            selectIndex(0, activeColumn);
        } else if (key == SDLK_END) {
            const auto &values = activeColumn == 1 ? races : options;
            selectIndex(static_cast<int>(values.size()) - 1, activeColumn);
        }
    }
    return true;
}

bool CGameCampaignBrowserPanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (!managedChoices) {
        return CGamePanel::mouseEvent(gui, type, button, x, y);
    }
    if (button == SDL_BUTTON_LEFT) {
        const int target = hitTarget(x, y);
        if (type == SDL_MOUSEBUTTONDOWN) {
            pressedTarget = target;
        } else if (type == SDL_MOUSEBUTTONUP) {
            const bool activate = target >= 0 && target == pressedTarget;
            pressedTarget = -1;
            if (activate) {
                if (target == CONFIRM_TARGET) {
                    clickSelect(gui);
                } else if (target == BACK_TARGET) {
                    clickCancel(gui);
                } else if (target >= PAGE_TARGET) {
                    selectPage(target - PAGE_TARGET);
                } else {
                    activeColumn = target >= RACE_TARGET ? 1 : 0;
                    selectIndex(target - (activeColumn == 1 ? RACE_TARGET : 0), activeColumn);
                }
            }
        }
    }
    return true;
}

bool CGameCampaignBrowserPanel::mouseMotionEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int xrel,
                                                 int yrel) {
    if (managedChoices) {
        hoveredTarget = hitTarget(x, y);
        return true;
    }
    return CGamePanel::mouseMotionEvent(gui, type, x, y, xrel, yrel);
}

bool CGameCampaignBrowserPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX,
                                                int wheelY) {
    if (managedChoices) {
        if ((!compactLayout || activePage == (characterChoices ? 2 : 1)) && containsPoint(detailRect(), x, y)) {
            scrollDetail(-wheelY * 48);
        } else {
            if (!compactLayout)
                activeColumn = characterChoices && containsPoint(listRect(1), x, y) ? 1 : 0;
            moveSelection(-wheelY);
        }
    }
    return true;
}

bool CGameCampaignBrowserPanel::mouseCancelEvent(std::shared_ptr<CGui> gui, SDL_EventType type) {
    hoveredTarget = -1;
    pressedTarget = -1;
    return managedChoices || CGamePanel::mouseCancelEvent(gui, type);
}
