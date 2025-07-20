# Repository Guidelines

## Testing
Run `python3 test.py` from the repository root.
This test suite requires the compiled `_game` module.
If the module or dependencies are missing, tests may fail; note this in the
Testing section.

## Code Style
- Use four spaces for indentation in both Python and C++ files.
- Keep lines under 120 characters where practical.
- Python variable and function names should be in `snake_case`.
- C++ class names should use `CamelCase`.

## Commit Messages
Describe changes clearly in the commit message.
If multiple logical changes are made, separate them into individual commits when
possible.

## Adding Item Types
Follow these steps whenever you introduce a new building, potion, effect, tile or other item type:

1. **Python plugin**
    - Add the class in a suitable file under `res/plugins/`.
    - Each plugin defines a `load(context)` function.
      Declare classes inside and decorate them with `@register(context)` so they
      become available to the game.

2. **Configuration entry**
    - Insert a new entry in the matching JSON file under `res/config/`.
      For example `items.json` for equipment or `potions.json` for potions.
    - The entry key is the item id used elsewhere.
      Specify the class name and any properties required by the object.

3. **Map update**
    - Reference the new item from map configuration files
      (such as `res/maps/nouraajd/config.json`).
      Use a `ref` field to point at the id from step 2, or define a class
      directly via a `class` field.

4. **Cross check ids**
    - Verify that the id in the config file matches the id used in the map and in
      any script calls like `createObject('YourItemId')`.
    - Mis‑matched ids will cause runtime errors when the map tries to spawn the item.

5. **Dialogs and dialog options**
    - To interact with the new item via dialog, add a new `CDialog` object to the
      map config or script.
    - Dialog states (`CDialogState`) can include options (`CDialogOption`) whose
      `action` or `nextStateId` references the item id or a method defined in
      your dialog class.
    - Ensure that every state and option id used in the JSON matches the definitions in the dialog class.

After adding the new item type, run `python3 test.py` to confirm that loading the game still works.
