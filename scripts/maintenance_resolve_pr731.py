from __future__ import annotations

from pathlib import Path


def unique_index(lines: list[str], target: str, start: int = 0, end: int | None = None) -> int:
    end = len(lines) if end is None else end
    matches = [index for index in range(start, end) if lines[index] == target]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one line {target!r}, found {len(matches)} in range {start}:{end}.")
    return matches[0]


def function_range(lines: list[str], signature: str, next_prefix: str = "    def ") -> tuple[int, int]:
    start = unique_index(lines, signature)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith(next_prefix) or lines[index] == "    @game_test":
            return start, index
    return start, len(lines)


def insert_after_cpp_function(path: Path, signature_prefix: str, block: str, sentinel: str) -> None:
    text = path.read_text(encoding="utf-8")
    if sentinel in text:
        return
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith(signature_prefix)]
    if len(starts) != 1:
        raise RuntimeError(f"Expected one C++ function matching {signature_prefix!r}, found {len(starts)}.")
    depth = 0
    opened = False
    function_end: int | None = None
    for index in range(starts[0], len(lines)):
        depth += lines[index].count("{")
        if "{" in lines[index]:
            opened = True
        depth -= lines[index].count("}")
        if opened and depth == 0:
            function_end = index
            break
    if function_end is None:
        raise RuntimeError(f"Could not find C++ function end for {signature_prefix!r}.")
    lines[function_end + 1 : function_end + 1] = [""] + block.splitlines()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def patch_inventory_panel() -> None:
    cpp = Path("src/gui/panel/CGameInventoryPanel.cpp")
    cpp_lines = cpp.read_text(encoding="utf-8").splitlines()
    if '#include "core/CSlotConfig.h"' not in cpp_lines:
        include_index = unique_index(cpp_lines, '#include "core/CMap.h"')
        cpp_lines.insert(include_index + 1, '#include "core/CSlotConfig.h"')
        cpp.write_text("\n".join(cpp_lines) + "\n", encoding="utf-8")

    cpp_text = cpp.read_text(encoding="utf-8")
    helper_sentinel = "bool drag_release_over_inventory_list"
    if helper_sentinel not in cpp_text:
        helper = '''bool drag_release_over_inventory_list(CGameInventoryPanel &panel, const std::shared_ptr<CGui> &gui) {
    if (!gui || !gui->hasDragSession()) {
        return false;
    }
    const auto *session = gui->getDragSession();
    for (const auto &child : panel.getChildren()) {
        auto list = vstd::cast<CListView>(child);
        if (!list || (list->getCollection() != INVENTORY_COLLECTION && list->getCollection() != EQUIPPED_COLLECTION)) {
            continue;
        }
        auto rect = list->getRect();
        if (rect && session->current.x >= rect->x && session->current.x < rect->x + rect->w &&
            session->current.y >= rect->y && session->current.y < rect->y + rect->h) {
            return true;
        }
    }
    return false;
}
'''
        namespace_end = cpp_text.find("} // namespace")
        if namespace_end < 0:
            raise RuntimeError("CGameInventoryPanel.cpp namespace end was not found.")
        cpp_text = cpp_text[:namespace_end] + helper + cpp_text[namespace_end:]
        cpp.write_text(cpp_text, encoding="utf-8")

    insert_after_cpp_function(
        cpp,
        "bool CGameInventoryPanel::inventoryDragStart(",
        '''void CGameInventoryPanel::inventoryDragCancel(std::shared_ptr<CGui> gui, int index,
                                                    std::shared_ptr<CGameObject> object) {
    if (drag_release_over_inventory_list(*this, gui)) {
        return;
    }
    auto item = usable_item(object);
    auto player = inventory_player(gui);
    if (!player || !item || !player->hasInInventory(item)) {
        return;
    }
    selectedEquipped.reset();
    selectedInventory = item;
    refreshViews();
}''',
        "CGameInventoryPanel::inventoryDragCancel",
    )
    insert_after_cpp_function(
        cpp,
        "bool CGameInventoryPanel::equippedDragStart(",
        '''void CGameInventoryPanel::equippedDragCancel(std::shared_ptr<CGui> gui, int index,
                                                   std::shared_ptr<CGameObject> object) {
    if (drag_release_over_inventory_list(*this, gui)) {
        return;
    }
    auto item = usable_item(object);
    auto player = inventory_player(gui);
    const std::string slotName = vstd::str(index);
    if (!player || !item || !slot_exists(gui, slotName) || player->getItemAtSlot(slotName) != item) {
        return;
    }
    selectedInventory.reset();
    selectedEquipped = item;
    refreshViews();
}''',
        "CGameInventoryPanel::equippedDragCancel",
    )

    header = Path("src/gui/panel/CGameInventoryPanel.h")
    header_lines = header.read_text(encoding="utf-8").splitlines()
    if not any("inventoryDragCancel" in line for line in header_lines):
        metadata = unique_index(
            header_lines,
            "        V_METHOD(CGameInventoryPanel, inventoryDragStart, bool, std::shared_ptr<CGui>, int,",
        )
        header_lines[metadata + 2 : metadata + 2] = [
            "        V_METHOD(CGameInventoryPanel, inventoryDragCancel, void, std::shared_ptr<CGui>, int,",
            "                 std::shared_ptr<CGameObject>),",
        ]
        declaration = unique_index(
            header_lines,
            "    bool inventoryDragStart(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);",
        )
        header_lines[declaration + 1 : declaration + 1] = [
            "",
            "    void inventoryDragCancel(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);",
        ]
    if not any("equippedDragCancel" in line for line in header_lines):
        metadata = unique_index(
            header_lines,
            "        V_METHOD(CGameInventoryPanel, equippedDragStart, bool, std::shared_ptr<CGui>, int,",
        )
        header_lines[metadata + 2 : metadata + 2] = [
            "        V_METHOD(CGameInventoryPanel, equippedDragCancel, void, std::shared_ptr<CGui>, int,",
            "                 std::shared_ptr<CGameObject>),",
        ]
        declaration = unique_index(
            header_lines,
            "    bool equippedDragStart(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);",
        )
        header_lines[declaration + 1 : declaration + 1] = [
            "",
            "    void equippedDragCancel(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);",
        ]
    header.write_text("\n".join(header_lines) + "\n", encoding="utf-8")

    panels = Path("res/config/panels.json")
    panel_text = panels.read_text(encoding="utf-8")
    if '"dragCancel": "inventoryDragCancel"' not in panel_text:
        anchor = '            "dragStart": "inventoryDragStart",\n'
        if panel_text.count(anchor) != 1:
            raise RuntimeError("Inventory dragStart JSON anchor was not unique.")
        panel_text = panel_text.replace(anchor, anchor + '            "dragCancel": "inventoryDragCancel",\n', 1)
    if '"dragCancel": "equippedDragCancel"' not in panel_text:
        anchor = '            "dragStart": "equippedDragStart",\n'
        if panel_text.count(anchor) != 1:
            raise RuntimeError("Equipped dragStart JSON anchor was not unique.")
        panel_text = panel_text.replace(anchor, anchor + '            "dragCancel": "equippedDragCancel",\n', 1)
    panels.write_text(panel_text, encoding="utf-8")


def patch_test_harness() -> None:
    path = Path("test.py")
    lines = path.read_text(encoding="utf-8").splitlines()

    start, _ = function_range(lines, "def activate_list_cell(list_view, gui, column, row, button=SDL_BUTTON_LEFT):", "def ")
    expected = [
        "def activate_list_cell(list_view, gui, column, row, button=SDL_BUTTON_LEFT):",
        "    tile = list_view.getTileSize()",
        "    list_view.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, button, column * tile + tile // 2, row * tile + tile // 2)",
    ]
    if lines[start : start + 3] != expected:
        raise RuntimeError("activate_list_cell body does not match current main.")
    lines[start : start + 3] = [
        expected[0],
        expected[1],
        "    x = column * tile + tile // 2",
        "    y = row * tile + tile // 2",
        "    list_view.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, button, x, y)",
        "    list_view.mouseEvent(gui, SDL_MOUSEBUTTONUP, button, x, y)",
    ]

    start, end = function_range(
        lines,
        "def click_first_list_object(test_case, list_view, gui, predicate=None, button=SDL_BUTTON_LEFT):",
        "def ",
    )
    press = unique_index(lines, "                    graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, button, 1, 1)", start, end)
    lines[press : press + 1] = [
        "                    if graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, button, 1, 1):",
        "                        tile = list_view.getTileSize()",
        "                        list_view.mouseEvent(",
        "                            gui, SDL_MOUSEBUTTONUP, button, column * tile + tile // 2, row * tile + tile // 2",
        "                        )",
    ]

    start, end = function_range(lines, "    def test_inventory_double_select_uses_selected_item(self):")
    y_line = unique_index(lines, "        inventory_list.setYPrefferedSize(2)", start, end)
    if lines[y_line + 1] != "        inventory_list.refresh()":
        raise RuntimeError("Double-select refresh anchor changed.")
    lines.insert(y_line + 1, '        inventory_list.setDragStart("")')

    start, end = function_range(lines, "    def test_fight_panel_callbacks_and_list_views(self):")
    loop = unique_index(lines, "        for list_view in (inventory_list, equipped_list):", start, end)
    allow = unique_index(lines, "            list_view.setAllowOversize(True)", loop, min(end, loop + 12))
    if lines[allow + 1] != "            list_view.refresh()":
        raise RuntimeError("Fight-panel list refresh anchor changed.")
    lines[allow + 1 : allow + 1] = [
        '            list_view.setDragStart("")',
        '            list_view.setDragValidate("")',
        '            list_view.setDrop("")',
    ]

    start, end = function_range(lines, "    def test_inventory_quest_item_selection_is_ignored(self):")
    assert_line = unique_index(
        lines,
        '        self.assertEqual(0, selected_after_quest_click.get("equippedCollection", 0))',
        start,
        end,
    )
    lines[assert_line + 1 : assert_line + 1] = [
        "",
        '        inventory_list = find_list_view(panel, "inventoryCollection")',
        '        equipped_list = find_list_view(panel, "equippedCollection")',
        "        item_column, item_row, _ = find_visible_list_cell_by_type(",
        '            inventory_list, g.getGui(), "letterToBeren"',
        "        )",
        "        start_x, start_y = list_cell_center(inventory_list, item_column, item_row)",
        "        target_x, target_y = list_cell_center(equipped_list, 0, 0)",
        "        weapon_before = player.getWeapon().getTypeId() if player.getWeapon() else None",
        "",
        "        push_sdl_mouse_button_event(start_x, start_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONDOWN)",
        "        pump_event_loop(3)",
        "        self.assertFalse(g.getGui().hasDragSession())",
        "        self.assertFalse(g.getGui().hasPointerCapture())",
        "",
        "        push_sdl_mouse_motion_event(target_x, target_y, target_x - start_x, target_y - start_y)",
        "        push_sdl_mouse_button_event(target_x, target_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONUP)",
        "        pump_event_loop(5)",
        "",
        "        weapon_after = player.getWeapon().getTypeId() if player.getWeapon() else None",
        '        self.assertEqual(1, player.countItems("letterToBeren"))',
        "        self.assertEqual(weapon_before, weapon_after)",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    patch_inventory_panel()
    patch_test_harness()
