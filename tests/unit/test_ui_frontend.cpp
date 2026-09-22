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
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CJsonUtil.h"
#include "core/CMap.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CUiArtwork.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CGameCampaignBrowserPanel.h"
#include "gui/panel/CGameCampaignPanel.h"
#include "handler/CGuiHandler.h"
#include "handler/CObjectHandler.h"
#include "test_harness.h"
#include <cstdio>

#include <pybind11/embed.h>

namespace {
void renderBrowser(const std::shared_ptr<CGameCampaignBrowserPanel> &browser, const std::shared_ptr<CGui> &gui,
                   const std::shared_ptr<SDL_Rect> &bounds) {
    if (!browser->getLayout())
        browser->setLayout(std::make_shared<CLayout>());
    browser->getLayout()->setRuntimeRect(bounds);
    browser->renderObject(gui, bounds, 0);
}

void testChoiceParsingPreservesOrderAndRejectsAmbiguousIds() {
    const auto choices = CGameCampaignBrowserPanel::parseChoices(R"([
        {"id":"zeta","label":"Same","detail":"First"},
        {"id":"alpha","label":"Same","detail":"Second","enabled":false}
    ])");
    expect_true(choices.size() == 2 && choices[0].id == "zeta" && choices[1].id == "alpha",
                "ordered choices must preserve caller order even when labels are equal");
    expect_true(choices[0].enabled && !choices[1].enabled, "unavailable choices must stay unavailable");
    for (const auto *invalid :
         {R"({})", R"([{"id":"","label":"Empty"}])", R"([{"id":"same","label":"One"},{"id":"same","label":"Two"}])",
          R"([{"id":"missingLabel"}])", R"([{"id":"one","label":"One","image":42}])",
          R"([{"id":"one","label":"One","image":"images/../secret.png"}])"}) {
        bool rejected = false;
        try {
            CGameCampaignBrowserPanel::parseChoices(invalid);
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected, "malformed or ambiguous choices must be rejected");
    }
}

void testArtworkPreservesAspectAndReclaimsMissingImages() {
    const SDL_Rect bounds{20, 30, 900, 500};
    const auto landscape = UiArtwork::fit(1200, 600, bounds);
    const auto portrait = UiArtwork::fit(600, 1200, bounds);
    expect_true(landscape.w == 900 && landscape.h == 450 && portrait.w == 250 && portrait.h == 500,
                "authored artwork fits inside its bounds without distorting its aspect ratio");
    auto gui = std::make_shared<CGui>();
    auto texture = SDL_CreateTexture(gui->getRenderContext().getRenderer(), SDL_PIXELFORMAT_RGBA8888,
                                     SDL_TEXTUREACCESS_STATIC, 600, 1200);
    expect_true(texture != nullptr, "offscreen artwork fixture texture is available");
    const auto wide = UiArtwork::layout(gui, texture, bounds, false);
    expect_true(wide.image.w > 0 && wide.image.x + wide.image.w < wide.text.x && wide.inset == 0,
                "wide campaign artwork and readable text occupy separate columns");
    const auto compact = UiArtwork::layout(gui, texture, bounds, true);
    expect_true(compact.image.h <= bounds.h / 4 && compact.inset > compact.image.h && compact.text.w == bounds.w,
                "compact artwork becomes a modest thumbnail above full-width scrolling text");
    const auto missing = UiArtwork::layout(gui, nullptr, bounds, false);
    expect_true(missing.image.w == 0 && missing.text.w == bounds.w && missing.inset == 0,
                "missing artwork returns all available space to the text");
    SDL_DestroyTexture(texture);

    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    browser->configureChoices("Campaign", CGameCampaignBrowserPanel::parseChoices(R"([
        {"id":"first","label":"First","detail":"Introduction","image":"images/missing-artwork.png"},
        {"id":"second","label":"Second","detail":"Another introduction"}
    ])"),
                              "Begin", "Back");
    renderBrowser(browser, gui, std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 1800, 1000}));
    expect_true(browser->getSelectedImage() == "images/missing-artwork.png" && browser->getArtworkBounds().w == 0 &&
                    browser->getTextBounds().w == browser->getDetailViewport().w,
                "selected optional artwork remains attached to its choice and missing assets reclaim the column");
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_DOWN);
    expect_true(browser->getSelectedImage().empty() && !browser->hasChoice(),
                "moving to an unillustrated choice clears the previous image without confirming anything");

    auto reader = std::make_shared<CGameCampaignPanel>();
    reader->setArtwork("images/missing-artwork.png");
    reader->setBody("A readable chapter introduction.");
    reader->renderBody(gui, std::make_shared<SDL_Rect>(bounds), 0);
    expect_true(reader->getArtworkBounds().w == 0 && reader->getTextBounds().w == bounds.w,
                "chapter readers also reclaim absent artwork space");
}

void testChoiceSelectionRequiresConfirmationAndBlocksDisabledRows() {
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    browser->configureChoices("Inventory",
                              {{"disabled", "Same", "Not available", false}, {"available", "Same", "Ready", true}},
                              "Use", "Back");
    expect_true(!browser->hasChoice(), "previewing the initial row must not confirm a choice");
    browser->clickSelect(nullptr);
    expect_true(!browser->hasChoice(), "disabled preview rows cannot be confirmed");
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_DOWN);
    expect_true(browser->getSelectedId() == "available" && browser->getDetailText().find("Ready") != std::string::npos,
                "keyboard selection must update the stable id and description together");
    expect_true(!browser->hasChoice(), "moving selection must not activate it");
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_RETURN);
    expect_true(browser->awaitChoice() == "available", "Enter confirms the highlighted enabled stable id");
}

void testChoiceCancellationAndLongLists() {
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    std::vector<CGameCampaignBrowserPanel::ChoiceOption> rows;
    for (int i = 0; i < 50; ++i)
        rows.push_back({std::to_string(i), "Row", std::to_string(i), true});
    browser->configureChoices("Long list", rows, "Choose", "Back");
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_END);
    expect_true(browser->getSelectedId() == "49", "End reaches entries beyond the visible first page");
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_HOME);
    expect_true(browser->getSelectedId() == "0", "Home returns to the first entry");
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_ESCAPE);
    expect_true(browser->hasChoice() && browser->awaitChoice().empty(), "Escape cancels a highlighted choice");
    browser->configureChoices("Empty", {}, "Choose", "Back");
    browser->clickSelect(nullptr);
    expect_true(!browser->hasChoice(), "empty lists cannot confirm a stale previous choice");
}

void testCharacterPreviewDoesNotStartUntilExplicitConfirmation() {
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    browser->configureCharacterChoices(
        {{"warrior", "Warrior", "Strength 5", true, {{"river", "Strength 5\nAgility 7\nHealth 20"}}}},
        {{"human", "Human", "Balanced", true}, {"river", "River folk", "Agility +1", true}});
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_TAB);
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_DOWN);
    expect_true(browser->getDetailText().find("Agility 7") != std::string::npos &&
                    browser->getDetailText().find("Health 20") != std::string::npos,
                "the selected race must show the exact composed character preview");
    expect_true(!browser->hasChoice(), "choosing a class and race must not automatically begin the game");
    browser->clickSelect(nullptr);
    expect_true(browser->awaitCharacterChoice() == std::make_pair(std::string("warrior"), std::string("river")),
                "character confirmation returns both stable ids");
    browser->configureChoices("Reused browser", {{"first", "First", "", true}, {"second", "Second", "", true}},
                              "Choose", "Back");
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_DOWN);
    expect_true(browser->getSelectedId() == "second", "reusing the browser resets navigation to its active list");
}

void testNamedSaveInputEditingAndCancellation() {
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    browser->configureTextInput("Save", "Name your adventure", "Suggested name");
    browser->appendInput("Before the gate");
    expect_true(browser->getInputText() == "Before the gate", "typing replaces the selected suggestion");
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_BACKSPACE);
    expect_true(browser->getInputText() == "Before the gat", "Backspace edits the current input");
    browser->appendInput("e");
    browser->appendInput("\ninvalid");
    expect_true(browser->getInputText() == "Before the gate", "control characters cannot enter a single-line name");
    browser->clickSelect(nullptr);
    expect_true(browser->awaitChoice() == "Before the gate", "save name is returned only on confirmation");
    browser->configureTextInput("Save", "Name", "");
    browser->clickSelect(nullptr);
    expect_true(!browser->hasChoice(), "empty names cannot confirm");
    browser->appendInput("Discard me");
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_ESCAPE);
    expect_true(browser->awaitChoice().empty(), "Escape discards entered text");
}

void testCharacterBackPreservesPreviewWithoutConfirmingIt() {
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    const std::vector<CGameCampaignBrowserPanel::ChoiceOption> classes = {{"warrior", "Warrior", "Strength", true},
                                                                          {"mage", "Mage", "Magic", true}};
    const std::vector<CGameCampaignBrowserPanel::ChoiceOption> races = {{"human", "Human", "Balanced", true},
                                                                        {"river", "River folk", "Agility", true}};
    browser->configureCharacterChoices(classes, races);
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_DOWN);
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_TAB);
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_DOWN);
    browser->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_ESCAPE);
    expect_true(browser->awaitCharacterChoice() == std::make_pair(std::string(), std::string()),
                "Back never confirms the previewed character");
    const auto previous = browser->getPreviewedCharacter();
    browser->configureCharacterChoices(classes, races, previous);
    expect_true(browser->getPreviewedCharacter() == std::make_pair(std::string("mage"), std::string("river")) &&
                    !browser->hasChoice(),
                "returning to character creation restores both selections for review");
    browser->configureCharacterChoices({classes[0]}, {races[0]}, previous);
    expect_true(browser->getPreviewedCharacter() == std::make_pair(std::string("warrior"), std::string("human")),
                "removed or no-longer-permitted options cannot be restored from remembered selections");
}

void testManagementPanelsReuseStateAndDoNotStack() {
    auto game = std::make_shared<CGame>();
    for (const auto &[name, builder] : *CTypes::builders())
        game->getObjectHandler()->registerType(name, builder);
    for (const auto &[id, type] : std::map<std::string, std::string>{{"inventoryPanel", "CGameInventoryPanel"},
                                                                     {"characterPanel", "CGameCharacterPanel"},
                                                                     {"questPanel", "CGameQuestPanel"}}) {
        game->getObjectHandler()->registerConfig(
            id, CJsonUtil::from_string("{\"class\":\"" + type + "\",\"properties\":{}}", id));
    }
    auto gui = std::make_shared<CGui>();
    expect_true(SDL_GetCurrentVideoDriver() && std::string(SDL_GetCurrentVideoDriver()) == "dummy",
                "frontend tests require isolated dummy video; never a visible fallback");
    game->setGui(gui);
    gui->setGame(game);
    game->setMap(std::make_shared<CMap>());
    auto handler = game->getGuiHandler();
    auto inventory = handler->openPanel("inventoryPanel");
    inventory->setStringProperty("frontendSelection", "kept");
    auto journal = handler->openPanel("questPanel");
    expect_true(!inventory->getGui() && journal->getGui() == gui, "opening Journal hides Inventory");
    auto reopened = handler->openPanel("inventoryPanel");
    expect_true(reopened == inventory && reopened->getStringProperty("frontendSelection") == "kept",
                "reopening a management panel preserves its inspected item and scroll state");
    expect_true(!journal->getGui(), "only one major management panel is attached");
    handler->flipPanel("characterPanel", "c");
    expect_true(!inventory->getGui(), "management hotkey switching returns immediately without nested modal waits");
    game->setMap(std::make_shared<CMap>());
    expect_true(handler->openPanel("inventoryPanel") != inventory,
                "a different map receives fresh management panels rather than stale object references");
    game->getContext()->shutdown();
}

void testNarrowFrontendKeepsChoicesAndPreviewOnKeyboardPages() {
    auto gui = std::make_shared<CGui>();
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    browser->configureCharacterChoices(
        {{"warrior", "Warrior", "Health 20", true}},
        {{"human", "Human", "Balanced", true}, {"river", "River folk", "Agility +1", true}});
    renderBrowser(browser, gui, std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 900, 676}));
    expect_true(browser->isCompactLayout() && browser->getActivePage() == 0,
                "narrow character creation presents one readable region at a time");
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_TAB);
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_DOWN);
    expect_true(browser->getActivePage() == 1 && browser->getDetailText().find("River folk") != std::string::npos,
                "Tab reaches race selection and arrows change the preview without starting");
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_TAB);
    expect_true(browser->getActivePage() == 2 && !browser->hasChoice(),
                "the character preview has its own keyboard-accessible page");
    renderBrowser(browser, gui, std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 1800, 1000}));
    expect_true(!browser->isCompactLayout(), "a wide viewport restores the class, race and preview columns");
    browser->configureChoices("Choose", {{"one", "First", "Details", true}}, "Accept", "Back");
    renderBrowser(browser, gui, std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 900, 676}));
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_TAB);
    expect_true(browser->getActivePage() == 1 && !browser->hasChoice(),
                "compact general choices expose details through Tab without activating the choice");
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_RETURN);
    expect_true(browser->awaitChoice() == "one", "explicit confirmation remains available from the details page");
}

void testEnlargedCharacterPreviewRetainsReadableViewport() {
    auto gui = std::make_shared<CGui>();
    gui->setNumericProperty("width", 1280);
    gui->setNumericProperty("height", 720);
    expect_true(gui->applyUiPreferences(R"({"uiScale":200,"textScale":200})"), "enlarged preferences apply");
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    browser->configureCharacterChoices(
        {{"warrior",
          "Warrior",
          "",
          true,
          {{"human", "Strength 14\nAgility 6\nStamina 11\nIntelligence 4\nHealth 77\nMana 98\nEquipment: Sword"}}}},
        {{"human", "Human", "Balanced", true}});
    const auto bounds = std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 1202, 676});
    renderBrowser(browser, gui, bounds);
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_TAB);
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_TAB);
    renderBrowser(browser, gui, bounds);
    const auto viewport = browser->getDetailViewport();
    const auto lineHeight = gui->getTextManager()->measureText("Ag", viewport.w, "body").second;
    expect_true(viewport.h >= 200 && viewport.h >= lineHeight * 4,
                "720p at 200 percent keeps at least four full character-preview lines above the actions");
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_PAGEDOWN);
    expect_true(browser->getDetailScrollOffset() > 0 && !browser->hasChoice(),
                "keyboard readers can reach overflow details without starting the adventure");
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_HOME);
    expect_true(browser->getDetailScrollOffset() == 0, "Home returns to the start of the enlarged preview");
    std::vector<CGameCampaignBrowserPanel::ChoiceOption> rows;
    for (int index = 0; index < 20; ++index)
        rows.push_back({std::to_string(index), "Choice " + std::to_string(index), "Details", true});
    browser->configureChoices("Long list", rows, "Open", "Back");
    renderBrowser(browser, gui, bounds);
    const auto choices = browser->getChoiceViewport();
    const auto action = browser->getConfirmationBounds();
    const auto rangeLine = gui->getTextManager()->measureText("1-2 / 20", choices.w, "small").second;
    expect_true(choices.y + choices.h + rangeLine + 4 <= action.y,
                "overflow list counts retain their own line above the confirmation controls");
    gui->applyUiPreferences("{}");
}

void testContinueReadersAllowEscapeAndCloseWithoutStartingAChapter() {
    auto reader = std::make_shared<CGameCampaignPanel>();
    reader->setBody("A letter whose contents are already recorded in History.");
    reader->setActionLabel("Continue");
    expect_true(reader->getCloseable(), "Continue readers expose the shared close control");
    reader->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_ESCAPE);
    expect_true(reader->isDismissed() && reader->awaitDismissal(), "Escape acknowledges an already-resolved reader");

    auto gui = std::make_shared<CGui>();
    auto closeReader = std::make_shared<CGameCampaignPanel>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(40, 30, 800, 600);
    closeReader->setLayout(layout);
    closeReader->setActionLabel("Continue");
    gui->pushChild(closeReader);
    const auto rect = layout->getRect(closeReader);
    SDL_Event click{};
    click.button.button = SDL_BUTTON_LEFT;
    click.button.x = rect->x + rect->w - 20;
    click.button.y = rect->y + 20;
    click.type = SDL_MOUSEBUTTONDOWN;
    gui->event(&click);
    click.type = SDL_MOUSEBUTTONUP;
    gui->event(&click);
    expect_true(!closeReader->getGui(), "the shared close control dismisses the Continue reader on a paired click");

    auto briefing = std::make_shared<CGameCampaignPanel>();
    briefing->setActionLabel("Begin chapter");
    briefing->keyboardEvent(nullptr, SDL_KEYDOWN, SDLK_ESCAPE);
    expect_true(!briefing->getCloseable() && !briefing->isDismissed(),
                "Escape cannot bypass a chapter briefing's explicit Begin chapter action");
}

void testLongReaderRetainsItsEndingBeyondTheTextCacheEntryLimit() {
    auto gui = std::make_shared<CGui>();
    auto reader = std::make_shared<CGameCampaignPanel>();
    reader->setActionLabel("Continue");
    std::string letter;
    for (int index = 0; index < 180; ++index)
        letter += "The old road still carries the names of those who left. ";
    letter += "\nFINAL LETTER MARKER - The promise is remembered.";
    reader->setBody(letter);
    auto viewport = std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 600, 280});
    reader->renderBody(gui, viewport, 0);
    expect_true(letter.size() > 4096 && reader->getVisibleBodyText().find("FINAL LETTER MARKER") == std::string::npos,
                "a long reader begins at its authored opening");
    reader->keyboardEvent(gui, SDL_KEYDOWN, SDLK_END);
    reader->renderBody(gui, viewport, 0);
    expect_true(reader->getVisibleBodyText().find("FINAL LETTER MARKER") != std::string::npos && !reader->isDismissed(),
                "End reaches the actual ending beyond 4096 bytes without dismissing the reader");
    const auto loads = gui->getTextManager()->getTextureLoadCount();
    reader->renderBody(gui, viewport, 0);
    expect_true(gui->getTextManager()->getTextureLoadCount() == loads,
                "an unchanged reader reuses measured paragraphs");
    gui->applyUiPreferences(R"({"textScale":200})");
    reader->renderBody(gui, viewport, 0);
    reader->keyboardEvent(gui, SDL_KEYDOWN, SDLK_END);
    reader->renderBody(gui, viewport, 0);
    expect_true(reader->getVisibleBodyText().find("FINAL LETTER MARKER") != std::string::npos,
                "resizing text reflows the complete reader, including its ending");
    reader->setBody("A replacement letter.");
    reader->renderBody(gui, viewport, 0);
    expect_true(reader->getVisibleBodyText().find("A replacement letter.") != std::string::npos,
                "replacing reader content clears its previous scroll position and layout");
    gui->applyUiPreferences("{}");
}

void testLongChoiceDetailsRemainReadableWithoutConfirmingTheirAction() {
    auto gui = std::make_shared<CGui>();
    auto browser = std::make_shared<CGameCampaignBrowserPanel>();
    std::string detail;
    for (int index = 0; index < 180; ++index)
        detail += "The chosen road leads through remembered places and old promises. ";
    detail += "\nFINAL SCENARIO MARKER - A quiet arrival.";
    browser->configureChoices("Choose a scenario", {{"long", "The long road", detail, true}}, "Begin", "Back");
    auto bounds = std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 900, 676});
    renderBrowser(browser, gui, bounds);
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_TAB);
    renderBrowser(browser, gui, bounds);
    expect_true(detail.size() > 4096 &&
                    browser->getVisibleDetailText().find("FINAL SCENARIO MARKER") == std::string::npos,
                "a long selected description begins with its opening text");
    browser->keyboardEvent(gui, SDL_KEYDOWN, SDLK_END);
    renderBrowser(browser, gui, bounds);
    expect_true(browser->getVisibleDetailText().find("FINAL SCENARIO MARKER") != std::string::npos &&
                    !browser->hasChoice(),
                "End reaches the real description ending without selecting the action");
    const auto loads = gui->getTextManager()->getTextureLoadCount();
    renderBrowser(browser, gui, bounds);
    expect_true(gui->getTextManager()->getTextureLoadCount() == loads,
                "unchanged choice detail reuses paragraph metrics");
    browser->setDetailText("A replacement preview.");
    renderBrowser(browser, gui, bounds);
    expect_true(browser->getVisibleDetailText().find("A replacement preview.") != std::string::npos,
                "a changed description invalidates the old paragraph layout and scroll offset");
}

void testReaderLayoutKeepsLargeTextBetweenHeaderAndAction() {
    auto gui = std::make_shared<CGui>();
    gui->setNumericProperty("width", 1280);
    gui->setNumericProperty("height", 720);
    gui->applyUiPreferences(R"({"uiScale":100,"textScale":200})");
    auto reader = std::make_shared<CGameCampaignPanel>();
    reader->setTitle("Letter from Rolf");
    reader->setActionLabel("Continue");
    reader->setLayout(std::make_shared<CLayout>());
    auto body = std::make_shared<CWidget>();
    body->setLayout(std::make_shared<CLayout>());
    body->setStringProperty("render", "renderBody");
    auto button = std::make_shared<CButton>();
    button->setLayout(std::make_shared<CLayout>());
    button->setStringProperty("click", "clickAction");
    button->setText("Continue");
    reader->pushChild(body);
    reader->pushChild(button);
    gui->pushChild(reader);
    const auto bounds = std::make_shared<SDL_Rect>(SDL_Rect{0, 0, 1200, 676});
    reader->getLayout()->setRuntimeRect(bounds);
    reader->renderObject(gui, bounds, 0);
    const auto bodyRect = body->getLayout()->getRect(body);
    const auto actionRect = button->getLayout()->getRect(button);
    const auto actionTextHeight = gui->getTextManager()->measureText("Continue", actionRect->w, "body").second;
    expect_true(bodyRect->y >= reader->getShellHeaderHeight(gui) && bodyRect->h >= 200,
                "large reader text starts below the measured title and keeps a usable viewport");
    expect_true(bodyRect->y + bodyRect->h < actionRect->y && actionRect->h >= actionTextHeight &&
                    actionRect->y + actionRect->h <= bounds->h,
                "the complete action label stays below the reader within the panel");
    gui->applyUiPreferences("{}");
}
} // namespace

int main() {
    const char *preferences = "ui-frontend-preferences.json";
    std::remove(preferences);
    SDL_setenv("GAME_UI_PREFERENCES_PATH", preferences, 1);
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    pybind11::scoped_interpreter guard{};
    type_registration::registerCoreTypes();
    type_registration::registerObjectTypes();
    type_registration::registerHandlerTypes();
    type_registration::registerGuiTypes();
    type_registration::registerGuiPanelTypes();
    type_registration::registerGuiWidgetTypes();
    type_registration::registerGuiAnimationTypes();
    testChoiceParsingPreservesOrderAndRejectsAmbiguousIds();
    testArtworkPreservesAspectAndReclaimsMissingImages();
    testChoiceSelectionRequiresConfirmationAndBlocksDisabledRows();
    testChoiceCancellationAndLongLists();
    testCharacterPreviewDoesNotStartUntilExplicitConfirmation();
    testNamedSaveInputEditingAndCancellation();
    testCharacterBackPreservesPreviewWithoutConfirmingIt();
    testManagementPanelsReuseStateAndDoNotStack();
    testNarrowFrontendKeepsChoicesAndPreviewOnKeyboardPages();
    testEnlargedCharacterPreviewRetainsReadableViewport();
    testContinueReadersAllowEscapeAndCloseWithoutStartingAChapter();
    testLongReaderRetainsItsEndingBeyondTheTextCacheEntryLimit();
    testLongChoiceDetailsRemainReadableWithoutConfirmingTheirAction();
    testReaderLayoutKeepsLargeTextBetweenHeaderAndAction();
    std::remove(preferences);
    return finish_tests();
}
