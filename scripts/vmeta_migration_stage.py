from pathlib import Path
import json
import os
import subprocess

changed = []
def replace(path, old, new, count):
    file = Path(path)
    text = file.read_text()
    if text.count(old) != count:
        raise RuntimeError(f'{path}: expected {count} matches, got {text.count(old)}')
    file.write_text(text.replace(old, new))
    if path not in changed:
        changed.append(path)

old = 'std::unordered_map<std::pair<std::type_index, std::type_index>, std::shared_ptr<CSerializerBase>>'
new = 'std::unordered_map<std::pair<std::type_index, std::type_index>, std::shared_ptr<CSerializerBase>, vstd::pair_hash>'
replace('src/core/CTypes.h', old, new, 1)
replace('src/core/CTypes.cpp', old, new, 2)
replace('src/gui/CTextManager.h', 'std::unordered_map<std::pair<std::string, int>, fn::sdl::TexturePtr>', 'std::unordered_map<std::pair<std::string, int>, fn::sdl::TexturePtr, vstd::pair_hash>', 1)
replace('src/gui/panel/CListView.h', 'std::unordered_map<std::pair<int, int>, std::shared_ptr<CProxyGraphicsObject>>', 'std::unordered_map<std::pair<int, int>, std::shared_ptr<CProxyGraphicsObject>, vstd::pair_hash>', 1)
old = 'std::unordered_set<std::pair<int, int>>'
new = 'std::unordered_set<std::pair<int, int>, vstd::pair_hash>'
replace('src/gui/CTextureCache.h', old, new, 1)
replace('src/gui/CTextureCache.cpp', old, new, 6)

file = Path('src/core/CGlobal.h')
text = file.read_text()
marker = "// vstd's public meta macros currently cast accessors"
if text.count(marker) != 1:
    raise RuntimeError('CGlobal.h: compatibility shim boundary not found')
file.write_text(text[:text.index(marker)] + 'static_assert(vstd::meta_api_version >= 2);\n')
changed.append(str(file))

replace('tests/unit/test_vstd.cpp', '#include "core/CUtil.h"', '#include "core/CUtil.h"\n#include "core/CTypes.h"\n#include "object/CGameObject.h"', 1)
fixture = r'''
struct MetaIntegrationObject : CGameObject {
    V_META_NAMED(MetaIntegrationObject, CGameObject, "tests::MetaIntegrationObject",
                 V_PROPERTY(MetaIntegrationObject, std::string, probeText, getProbeText, setProbeText),
                 V_METHOD(MetaIntegrationObject, payload, std::any),
                 V_METHOD(MetaIntegrationObject, unpack, int, std::any),
                 V_METHOD(MetaIntegrationObject, measure, int, const std::string&),
                 V_METHOD(MetaIntegrationObject, mutate, void, int&))
  public:
    std::string probeText;
    const std::string& getProbeText() const { return probeText; }
    void setProbeText(const std::string& value) { probeText = value; }
    std::any payload() const { return 42; }
    int unpack(std::any value) const { return std::any_cast<int>(value); }
    int measure(const std::string& value) const { return static_cast<int>(value.size()); }
    void mutate(int& value) { ++value; }
};

void test_vmeta_game_object_integration() {
    std::shared_ptr<CGameObject> object = std::make_shared<MetaIntegrationObject>();
    auto meta = object->meta();
    const std::string text(256, 'x');
    object->setProperty("probeText", text);
    expect_true(object->getProperty<std::string>("probeText") == text,
                "derived const-reference accessors should work through the base game-object API");
    auto returned = meta->invoke_method<std::string>("getProbeText", object);
    meta->invoke_method<void>("setProbeText", object, std::string("changed"));
    expect_true(returned == text, "reflective results should own reference-returned text");
    expect_true(object->getProperty<std::string>("probeText") == "changed",
                "reference-taking setters should work without the game macro shim");
    expect_true(std::any_cast<int>(meta->invoke_method<std::any>("payload", object)) == 42,
                "std::any method results should expose the erased payload");
    expect_true(meta->invoke_method<int>("unpack", object, std::any(42)) == 42,
                "std::any method parameters should accept erased payloads");
    object->setProperty("probePayload", std::any(42));
    expect_true(std::any_cast<int>(object->getProperty<std::any>("probePayload")) == 42,
                "dynamic std::any properties should retain their values");
    object->setProperty("probePayload", std::any(std::string("next")));
    expect_true(std::any_cast<std::string>(object->getProperty<std::any>("probePayload")) == "next",
                "dynamic std::any properties should permit a different contained type");
    vstd::register_any_type<std::string, std::string>();
    expect_true(meta->invoke_method<int>("measure", object, text) == 256,
                "identity conversion registration must not invalidate reference arguments");
    int mutableValue = 7;
    meta->invoke_method<void>("mutate", object, std::ref(mutableValue));
    expect_true(mutableValue == 8, "explicit reference arguments should mutate the caller's value");
    object->setProperty("probeHealth", 100);
    auto copied = std::make_shared<MetaIntegrationObject>(*std::dynamic_pointer_cast<MetaIntegrationObject>(object));
    copied->setProperty("probeHealth", 25);
    expect_true(object->getProperty<int>("probeHealth") == 100,
                "copying a game object must not alias its dynamic property storage");
    expect_true(copied->getProperty<int>("probeHealth") == 25,
                "the copy should retain its own dynamic property value");
}

void test_vmeta_explicit_pair_hashers() {
    std::unordered_map<std::pair<int, int>, int, vstd::pair_hash> coordinates;
    coordinates[{1, 2}] = 3;
    coordinates[{2, 1}] = 4;
    expect_true(coordinates.at({1, 2}) == 3 && coordinates.at({2, 1}) == 4,
                "coordinate cache hashing must distinguish ordered pairs");
    std::unordered_map<std::pair<std::string, int>, int, vstd::pair_hash> text;
    text[{"label", 120}] = 5;
    expect_true(text.at({"label", 120}) == 5, "text cache keys should work with an explicit pair hasher");
    std::unordered_set<std::pair<int, int>, vstd::pair_hash> pixels{{1, 2}, {2, 1}};
    expect_true(pixels.size() == 2, "texture masks should retain distinct coordinate pairs");
    expect_true(!CTypes::serializers()->empty(), "the serializer registry should initialize with the explicit hasher");
}
'''
replace('tests/unit/test_vstd.cpp', '} // namespace\n\nint main()', fixture + '\n} // namespace\n\nint main()', 1)
replace('tests/unit/test_vstd.cpp', '    test_vstd_string_helpers();', '    test_vstd_string_helpers();\n    test_vmeta_game_object_integration();\n    test_vmeta_explicit_pair_hashers();', 1)

subprocess.run(['clang-format', '-i', *changed], check=True)
subprocess.run(['clang-format', '--dry-run', '--Werror', *changed], check=True)
subprocess.run(['git', 'diff', '--check'], check=True)
subprocess.run(['git', 'diff', '--stat'], check=True)
subprocess.run(['git', 'diff', '--', *changed], check=True)
entries = []
for path in changed:
    payload = json.dumps({'content': Path(path).read_text(), 'encoding': 'utf-8'})
    result = subprocess.run(['gh', 'api', '--method', 'POST', 'repos/' + os.environ['GITHUB_REPOSITORY'] + '/git/blobs', '--input', '-'], input=payload, text=True, capture_output=True, check=True)
    entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': json.loads(result.stdout)['sha']})
print('FORMATTED_TREE=' + json.dumps(entries))
