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
#pragma once

#include "CGamePanel.h"

#include <map>
#include <vector>

// Stable-ID campaign browser: campaign titles down the left column (built by
// CGuiHandler::showCampaignSelection), the highlighted campaign's description
// and chapter count on the right, and SELECT / CANCEL actions. Selection only
// begins after SELECT confirms a highlighted campaign; CANCEL, Escape, or the
// panel being torn down resolve to an empty campaign id.
class CGameCampaignBrowserPanel : public CGamePanel {
    V_META(CGameCampaignBrowserPanel, CGamePanel,
           V_PROPERTY(CGameCampaignBrowserPanel, std::string, selectedId, getSelectedId, setSelectedId),
           V_PROPERTY(CGameCampaignBrowserPanel, std::string, detailText, getDetailText, setDetailText),
           V_METHOD(CGameCampaignBrowserPanel, renderDetail, void, std::shared_ptr<CGui>, std::shared_ptr<SDL_Rect>,
                    int),
           V_METHOD(CGameCampaignBrowserPanel, clickSelect, void, std::shared_ptr<CGui>),
           V_METHOD(CGameCampaignBrowserPanel, clickCancel, void, std::shared_ptr<CGui>))

  public:
    struct ChoiceOption {
        std::string id;
        std::string label;
        std::string detail;
        bool enabled = true;
        std::map<std::string, std::string> previews;
        std::string image;
    };

    static std::vector<ChoiceOption> parseChoices(const std::string &choicesJson);

    void configureChoices(std::string title, std::vector<ChoiceOption> options, std::string actionLabel,
                          std::string backLabel);

    void configureCharacterChoices(std::vector<ChoiceOption> classes, std::vector<ChoiceOption> races,
                                   std::pair<std::string, std::string> previous = {});

    std::pair<std::string, std::string> getPreviewedCharacter() const;

    void configureTextInput(std::string title, std::string prompt, std::string initialValue);

    void appendInput(const std::string &text);

    std::string getInputText() const;

    bool isCompactLayout() const;

    int getActivePage() const;

    SDL_Rect getDetailViewport() const;

    SDL_Rect getChoiceViewport(int column = 0) const;

    SDL_Rect getConfirmationBounds() const;

    int getDetailScrollOffset() const;
    SDL_Rect getArtworkBounds() const { return artworkBounds; }
    SDL_Rect getTextBounds() const { return textBounds; }
    std::string getSelectedImage() const { return detailImage; }

    std::pair<std::string, std::string> awaitCharacterChoice();

    // Blocks until SELECT confirms a campaign, CANCEL/Escape aborts, or the
    // panel is torn down. Returns the confirmed stable campaign id, or "" for
    // every cancel path.
    std::string awaitChoice();

    bool hasChoice();

    std::string getSelectedId();

    void setSelectedId(std::string value);

    std::string getDetailText();

    std::string getVisibleDetailText() const;

    void setDetailText(std::string value);

    void renderDetail(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime);

    void clickSelect(std::shared_ptr<CGui> gui);

    void clickCancel(std::shared_ptr<CGui> gui);

    bool keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) override;

    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override;

    bool mouseMotionEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int xrel, int yrel) override;

    bool mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int x, int y, int wheelX, int wheelY) override;

    bool mouseCancelEvent(std::shared_ptr<CGui> gui, SDL_EventType type) override;

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) override;

  protected:
    bool event(std::shared_ptr<CGui> gui, SDL_Event *event) override;

  private:
    struct DetailParagraph {
        std::string text;
        int y;
        int height;
    };
    std::vector<DetailParagraph> detailParagraphs;
    int detailMeasuredWidth = 0;
    double detailMeasuredTextScale = 0;
    int detailMeasuredInset = -1;
    SDL_Rect artworkBounds{0, 0, 0, 0};
    SDL_Rect textBounds{0, 0, 0, 0};
    std::string detailImage;
    void selectIndex(int index, int column);
    void moveSelection(int delta);
    void updateDetail();
    bool canConfirm() const;
    int hitTarget(int x, int y) const;
    SDL_Rect listRect(int column) const;
    SDL_Rect detailRect() const;
    SDL_Rect actionRect() const;
    SDL_Rect backRect() const;
    SDL_Rect pageRect(int page) const;
    void selectPage(int page);
    void scrollDetail(int delta);

    std::string selectedId;
    std::string detailText;
    std::shared_ptr<std::string> choice;
    std::vector<ChoiceOption> options;
    std::vector<ChoiceOption> races;
    std::string title;
    std::string actionLabel = "Select";
    std::string backLabel = "Back";
    bool managedChoices = false;
    bool characterChoices = false;
    bool textInputMode = false;
    bool compactLayout = false;
    int activePage = 0;
    bool inputSelectAll = false;
    std::string inputText;
    std::string inputPrompt;
    int selectedIndex = -1;
    int selectedRaceIndex = -1;
    int activeColumn = 0;
    int listOffset = 0;
    int raceOffset = 0;
    int detailOffset = 0;
    int detailHeight = 0;
    int panelWidth = 1000;
    int panelHeight = 720;
    int rowHeight = 54;
    int measuredLabelWidth = 0;
    int measuredLabelLine = 0;
    int headerHeight = 108;
    int footerHeight = 126;
    int buttonHeight = 48;
    int hintHeight = 28;
    int hoveredTarget = -1;
    int pressedTarget = -1;
};
