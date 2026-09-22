/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "core/CStats.h"
#include "core/CLoader.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CUiPreferences.h"
#include "gui/CTooltip.h"
#include "gui/object/CWidget.h"
#include "gui/object/CSideBar.h"
#include "object/CPlayer.h"
#include "object/CMapObject.h"
#include "gui/panel/CGamePanel.h"
#include "gui/panel/CGameCampaignPanel.h"
#include "test_harness.h"
#include <pybind11/embed.h>
#include <cstdio>
#include <fstream>

class FocusTestPanel : public CGamePanel {
    V_META(FocusTestPanel, CGamePanel, V_METHOD(FocusTestPanel, activateControl, void, std::shared_ptr<CGui>))
  public:
    int activations = 0;
    void activateControl(std::shared_ptr<CGui>) { ++activations; }
};

class WorldInputProbe : public CGameGraphicsObject {
  public:
    int waits = 0;
    bool keyboardEvent(std::shared_ptr<CGui>, SDL_EventType type, SDL_Keycode key) override {
        if (type == SDL_KEYDOWN && key == SDLK_SPACE) {
            ++waits;
            return true;
        }
        return false;
    }
};

namespace {
void testPreferencesUseTheSdlEnvironmentOverride() {
    const auto *previous = SDL_getenv("GAME_UI_PREFERENCES_PATH");
    const std::string previousPath = previous ? previous : "";
    const char *path = "ui-foundations-preference-roundtrip.json";
    std::remove(path);
    SDL_setenv("GAME_UI_PREFERENCES_PATH", path, 1);
    auto game = std::make_shared<CGame>();
    auto gui = std::make_shared<CGui>();
    game->setGui(gui);
    gui->setGame(game);
    expect_true(gui->applyUiPreferences(R"({"uiScale":125,"textScale":150})"),
                "isolated preferences must be writable through SDL's environment override");
    {
        std::ifstream file(path);
        expect_true(file.good(), "preferences must be stored at the explicitly isolated path");
        if (file) {
            const std::string contents((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
            const auto stored = json::parse(contents);
            expect_true(stored.value("uiScale", 0) == 125 && stored.value("textScale", 0) == 150,
                        "the isolated preferences file must contain the accepted scales");
        }
    }
    std::remove(path);
    SDL_setenv("GAME_UI_PREFERENCES_PATH", previousPath.c_str(), 1);
}

void testPreferencesValidateBeforeApplying() {
    expect_true(UiPreferences::validate(UiPreferences::defaults()), "default preferences must be valid");
    for (const auto &invalid :
         {json{{"uiScale", 99}}, json{{"uiScale", 201}}, json{{"textScale", 125.0}}, json{{"uiScale", 4294967396LL}},
          json{{"tooltipDelayMs", -1}}, json{{"highContrast", "yes"}}, json{{"unknown", true}}}) {
        expect_true(!UiPreferences::validate(invalid), "invalid settings must fail before mutation");
    }
    auto duplicate = UiPreferences::defaults();
    duplicate["bindings"]["journal"] = "I";
    expect_true(!UiPreferences::validate(duplicate), "two actions cannot bind the same key");
    duplicate["bindings"]["journal"] = "Tab";
    expect_true(!UiPreferences::validate(duplicate), "focus navigation keys must remain reserved");
    duplicate["bindings"]["journal"] = "M";
    expect_true(!UiPreferences::validate(duplicate), "the expanded map shortcut cannot be shadowed by remapping");
    expect_true(!CMapLoader::saveWithResult(nullptr, "../invalid"), "save failures must be observable");
}

void testFocusActivationAndRestoration() {
    auto game = std::make_shared<CGame>();
    auto gui = std::make_shared<CGui>();
    game->setGui(gui);
    gui->setGame(game);
    auto panel = std::make_shared<FocusTestPanel>();
    auto shell = std::make_shared<CLayout>();
    shell->setRect(0, 0, 800, 600);
    panel->setLayout(shell);
    auto button = std::make_shared<CButton>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(24, 100, 240, 48);
    button->setLayout(layout);
    button->setClick("activateControl");
    panel->addChild(button);
    gui->pushChild(panel);
    SDL_Event event{};
    event.type = SDL_KEYDOWN;
    event.key.keysym.sym = SDLK_TAB;
    gui->event(&event);
    expect_true(gui->isFocused(button.get()), "Tab must focus the first enabled action");
    event.key.keysym.sym = SDLK_RETURN;
    gui->event(&event);
    expect_true(panel->activations == 1, "Enter must execute the focused action once");
    event.key.repeat = 1;
    gui->event(&event);
    expect_true(panel->activations == 1, "held activation input cannot repeat through modal UI");
    event.key.repeat = 0;
    button->setEnabled(false);
    gui->event(&event);
    expect_true(panel->activations == 1, "disabled actions cannot execute from old focus");
    button->setEnabled(true);
    auto nested = std::make_shared<CGamePanel>();
    nested->setLayout(shell);
    gui->pushChild(nested);
    event.key.keysym.sym = SDLK_ESCAPE;
    gui->event(&event);
    expect_true(gui->isFocused(button.get()), "dismissing a modal restores the previous control");
    expect_true(gui->findChild(panel) != nullptr, "closing the top panel must not close its owner");
    auto inspection = std::make_shared<CTooltip>();
    inspection->setLayout(shell);
    gui->pushChild(inspection);
    gui->event(&event);
    expect_true(gui->isFocused(button.get()), "dismissing pinned inspection must restore its source control");
    gui->pushChild(inspection);
    const auto activationsBeforeInspection = panel->activations;
    event = {};
    event.type = SDL_MOUSEBUTTONDOWN;
    event.button.button = SDL_BUTTON_LEFT;
    event.button.x = 40;
    event.button.y = 120;
    expect_true(gui->event(&event), "inspection dismissal must consume the press over an underlying action");
    event.type = SDL_MOUSEBUTTONUP;
    gui->event(&event);
    expect_true(!inspection->getParent() && panel->activations == activationsBeforeInspection,
                "inspection dismissal and release cannot activate the control underneath");
    game->setMap(std::make_shared<CMap>());
    expect_true(gui->findChild(panel) == nullptr, "scene changes must invalidate outgoing panels");
}

void testHeldDismissalCannotReachTheNextPanelOrWorld() {
    auto gui = std::make_shared<CGui>();
    auto world = std::make_shared<WorldInputProbe>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(0, 0, 800, 600);
    world->setLayout(layout);
    gui->addChild(world);
    auto openReader = [&]() {
        auto panel = std::make_shared<CGameCampaignPanel>();
        panel->setLayout(layout);
        panel->setActionLabel("Continue");
        gui->pushChild(panel);
        return panel;
    };
    auto first = openReader();
    SDL_Event event{};
    event.type = SDL_KEYDOWN;
    event.key.keysym.sym = SDLK_SPACE;
    gui->event(&event);
    expect_true(!first->getParent(), "a deliberate press acknowledges the current reader");
    event.key.repeat = 1;
    gui->event(&event);
    expect_true(world->waits == 0, "holding a reader dismissal key cannot wait a world turn");
    auto next = openReader();
    gui->event(&event);
    expect_true(next->getParent() == gui, "the same held press cannot acknowledge a subsequent reader");
    event.type = SDL_KEYUP;
    gui->event(&event);
    event.type = SDL_KEYDOWN;
    event.key.repeat = 0;
    gui->event(&event);
    expect_true(!next->getParent(), "a fresh press may acknowledge the next reader");
    event.type = SDL_KEYUP;
    gui->event(&event);
    event.type = SDL_KEYDOWN;
    gui->event(&event);
    event.key.repeat = 1;
    gui->event(&event);
    expect_true(world->waits == 2, "world wait and its repeat remain available after releasing modal input");
}

void testTextStyleCacheIsCorrectAndBounded() {
    auto gui = std::make_shared<CGui>();
    auto text = gui->getTextManager();
    auto body = text->measureText("Agpq", 300, "body");
    auto title = text->measureText("Agpq", 300, "title");
    expect_true(body.first > 0 && body.second > 0, "bundled fonts must render Unicode text");
    expect_true(title.second > body.second, "font roles must have separate metrics and cache entries");
    const auto count = text->getCachedTextureCount();
    for (int index = 0; index < 200; ++index)
        text->measureText("Agpq", 300, "body");
    expect_true(text->getCachedTextureCount() == count, "repeated metrics must reuse the style cache");
    auto rect = CUtil::rect(0, 0, 300, 80);
    text->drawTextStyled("Agpq", rect, "body", {255, 0, 0, 255});
    expect_true(text->getCachedTextureCount() == count + 1, "text color must participate in the cache key");
    for (int index = 0; index < 550; ++index)
        text->measureText("Entry " + std::to_string(index), 300);
    expect_true(text->getCachedTextureCount() <= 512, "unbounded history cannot grow the text texture cache");
    expect_true(text->getCachedFontCount() <= 24, "font and glyph caches must stay bounded");
    text->clearCache();
    expect_true(text->getCachedTextureCount() == 0 && text->getCachedFontCount() == 0,
                "scale changes must discard obsolete text and font caches");
}

void testUnnamedGeneratedMapHudRenders() {
    auto game = std::make_shared<CGame>();
    auto gui = std::make_shared<CGui>();
    game->setGui(gui);
    gui->setGame(game);
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);
    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    auto stats = std::make_shared<CStats>();
    stats->setStamina(10);
    stats->setMainStat("stamina");
    player->setBaseStats(stats);
    map->setPlayer(player);
    auto hud = std::make_shared<CSideBar>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(1680, 0, 240, 240);
    hud->setLayout(layout);
    gui->addChild(hud);
    expect_true(map->getMapName().empty(), "generated-map fixture must have no authored resource name");
    try {
        hud->renderObject(gui, CUtil::rect(1680, 0, 240, 240), 0);
        expect_true(gui->getRenderContext().getStats().successfulCopies > 0,
                    "unnamed generated maps must render their location and player information");
    } catch (const std::exception &) {
        expect_true(false, "an unnamed generated map cannot throw while rendering the HUD");
    }
    gui->setWidth(1280);
    gui->setHeight(720);
    expect_true(gui->applyUiPreferences(R"({"uiScale":200,"textScale":200})"),
                "compact HUD fixture must apply enlarged text");
    for (const auto &[label, method] : std::map<std::string, std::string>{{"Inventory I", "clickInventory"},
                                                                          {"Journal J", "clickJournal"},
                                                                          {"Character C", "clickCharacter"},
                                                                          {"Pause Escape", "clickPause"}}) {
        auto button = std::make_shared<CButton>();
        button->setLayout(std::make_shared<CLayout>());
        button->setText(label);
        button->setClick(method);
        hud->addChild(button);
    }
    hud->renderObject(gui, layout->getRect(hud), 0);
    const auto dock = layout->getRect(hud);
    expect_true(dock->y > 360 && dock->y + dock->h <= 720 && dock->w <= 1060,
                "compact navigation must sit below the map center and beside the minimap");
    for (const auto &child : hud->getChildren()) {
        const auto control = child->getLayout()->getRect(child);
        auto button = vstd::cast<CButton>(child);
        const int inset = 16;
        const int textHeight = gui->getTextManager()->measureText(button->getText(), control->w - inset * 2).second;
        expect_true(control->h >= textHeight + inset * 2 && control->x >= 0 && control->x + control->w <= dock->w,
                    "compact navigation labels must fit their controls at enlarged text scale");
    }
}

void testCompactManagementControlsFitEnlargedText() {
    auto game = std::make_shared<CGame>();
    auto gui = std::make_shared<CGui>();
    game->setGui(gui);
    gui->setGame(game);
    gui->setWidth(1280);
    gui->setHeight(720);
    for (int uiScale : {100, 200}) {
        expect_true(gui->applyUiPreferences(json{{"uiScale", uiScale}, {"textScale", 200}}.dump()),
                    "compact layout preferences must apply");
        auto panel = std::make_shared<CGamePanel>();
        auto shell = std::make_shared<CLayout>();
        shell->setRect(38, 21, 1203, 677);
        panel->setLayout(shell);
        panel->setTitle("Inventory");
        auto content = std::make_shared<CWidget>();
        content->setLayout(std::make_shared<CLayout>());
        content->setStringProperty("uiGroup", "1:Items");
        panel->addChild(content);
        auto action = std::make_shared<CButton>();
        action->setText("Use selected item");
        auto actionLayout = std::make_shared<CLayout>();
        actionLayout->setRect(600, 616, 288, 40);
        action->setLayout(actionLayout);
        action->setBoolProperty("uiFooter", true);
        panel->addChild(action);
        gui->pushChild(panel);
        panel->renderShell(gui, shell->getRect(panel));
        const auto footer = actionLayout->getRect(action);
        const auto body = content->getLayout()->getRect(content);
        const int headingHeight = gui->getTextManager()->measureText("Inventory", 600, "heading").second;
        expect_true(panel->getShellHeaderHeight(gui) >= headingHeight + static_cast<int>(16 * gui->getUiScale()),
                    "panel headers must fit independently enlarged title text");
        expect_true(panel->getShellCloseWidth(gui) >= gui->getTextManager()->measureText("Close  ×", 0, "body").first,
                    "the visible close control must fit independently enlarged text");
        expect_true(body->y >= 21 + panel->getShellHeaderHeight(gui),
                    "management content must begin below the measured panel title");
        const int inset = static_cast<int>(8 * gui->getUiScale());
        const int textHeight = gui->getTextManager()->measureText(action->getText(), footer->w - inset * 2).second;
        expect_true(footer->h >= textHeight + inset * 2,
                    "compact action buttons must fit actual enlarged text and padding");
        expect_true(body->y + body->h < footer->y && footer->y + footer->h <= 698,
                    "content and actions must remain separated inside the 720p panel");
        expect_true(body->h >= 300, "compact cards must retain useful reading space at enlarged scale");
        panel->close();
    }
}

void testBlockedActionFeedbackIsReadOnlyAndSceneBound() {
    auto game = std::make_shared<CGame>();
    auto gui = std::make_shared<CGui>();
    auto map = std::make_shared<CMap>();
    game->setGui(gui);
    gui->setGame(game);
    map->setGame(game);
    game->setMap(map);
    auto gate = std::make_shared<CMapObject>();
    gate->setName("sealedGate");
    gate->setGame(game);
    map->addObject(gate);
    const auto turn = map->getTurn();
    gui->notifyAt(gate, "Requires one mage-wand.");
    expect_true(gui->getActionFeedback() == "Requires one mage-wand.",
                "resolved requirements must remain associated with their world target");
    expect_true(gui->getRecentNotification().empty(), "anchored feedback must not duplicate the activity toast");
    expect_true(gui->getUiHistory().find("Requires one mage-wand.") != std::string::npos && map->getTurn() == turn,
                "a blocked-action explanation must be recoverable without advancing a turn");
    map->removeObject(gate);
    expect_true(gui->getActionFeedback().empty(), "removed objects cannot retain a stale action annotation");
    map->addObject(gate);
    gui->notifyAt(gate, "Still sealed.");
    game->setMap(std::make_shared<CMap>());
    expect_true(gui->getActionFeedback().empty(), "scene transitions invalidate outgoing action feedback");
}
} // namespace

int main() {
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    const char *preferences = "ui-foundations-preferences.json";
    std::remove(preferences);
    SDL_setenv("GAME_UI_PREFERENCES_PATH", preferences, 1);
    pybind11::scoped_interpreter interpreter{};
    type_registration::registerCoreTypes();
    type_registration::registerObjectTypes();
    type_registration::registerHandlerTypes();
    type_registration::registerGuiTypes();
    type_registration::registerGuiPanelTypes();
    type_registration::registerGuiWidgetTypes();
    type_registration::registerGuiAnimationTypes();
    CTypes::register_type_metadata<FocusTestPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
    testPreferencesValidateBeforeApplying();
    testPreferencesUseTheSdlEnvironmentOverride();
    testFocusActivationAndRestoration();
    testHeldDismissalCannotReachTheNextPanelOrWorld();
    testTextStyleCacheIsCorrectAndBounded();
    testUnnamedGeneratedMapHudRenders();
    testCompactManagementControlsFitEnlargedText();
    testBlockedActionFeedbackIsReadOnlyAndSceneBound();
    std::remove(preferences);
    return finish_tests();
}
