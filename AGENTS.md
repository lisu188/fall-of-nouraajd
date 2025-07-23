# Repository Guidelines

## Testing
Run `python3 test.py` from the repository root.
This test suite requires the compiled `_game` module.
If the module or dependencies are missing, tests may fail; note this in the
Testing section.

## Code Style
- Use four spaces for indentation in both Python and C++ files.
- Python files are checked for indentation consistency during testing.
- Keep lines under 120 characters where practical.
- Python variable and function names should be in `snake_case`.
- C++ class names should use `CamelCase`.

## Commit Messages
Describe changes clearly in the commit message.
If multiple logical changes are made, separate them into individual commits when
possible.
- Keep your branch up to date with the main branch.


## Merging Main
Regularly merge the repository's main branch (`master`) into your feature branch to
stay up to date:
Resolve any conflicts and rerun `python3 test.py`.

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
    - Implement each custom `action` as a method on the Python dialog class.
      The method name must match the `action` string used in the JSON option.
    - The dialog panel only checks for state ids named `ENTRY` and `EXIT` when
      opening and closing dialogs. They are not keywords; use any id names as
      long as references match.

After adding the new item type, run `python3 test.py` to confirm that loading the game still works.
## Exposing C++ Types to Python
Follow these steps when making a new C++ class usable from Python:

1. **Create a wrapper**
    - Add a `CWrapper<MyClass>` specialization in `src/core/CWrapper.h`.
    - Implement wrappers for any methods Python should override.

2. **Update the module**
    - Edit `src/core/CModule.cpp` and declare the wrapper with
      `class_<CWrapper<MyClass>, bases<BaseClass>, boost::noncopyable,
      std::shared_ptr<CWrapper<MyClass>>>("MyClass")` inside
      `BOOST_PYTHON_MODULE(_game)`.
    - Register the wrapper in `src/core/CTypes.cpp` using
      `CTypes::register_type<CWrapper<MyClass>, MyClass, BaseClass>();`.

3. **Create the Python object**
    - Define a subclass in a plugin under `res/plugins/`.
    - Add it inside `load(context)` and decorate with `@register(context)`.

After exposing the new type, run `python3 test.py` to verify the bindings.

## Copyright
When modifying source files, update the copyright year in
the header comments to 2025.
