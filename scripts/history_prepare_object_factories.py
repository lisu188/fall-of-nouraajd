"""Pinned Linux build repairs for the turn callback and factory revisions."""

import hashlib
from pathlib import Path

PROFILES = {
    "75c6918509bb39a489d979fb0dfcdfd103fcfbf6": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "d71895c9b668ad3b616bbeb81995b24fd01b3b24ccda8ad518ca27a27f16ddb6",
            "ac6bb906f168c4265ac4cbed6c9c8782ce316a3b80a9eaee198fcc067ba6343c",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'CScriptEngine::~CScriptEngine() {\n', b'CScriptEngine::~CScriptEngine() {\n\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n')],
        ),
    },
    "f6b016214b3367ba302c2a6ed47face5d27f3c13": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "d71895c9b668ad3b616bbeb81995b24fd01b3b24ccda8ad518ca27a27f16ddb6",
            "ac6bb906f168c4265ac4cbed6c9c8782ce316a3b80a9eaee198fcc067ba6343c",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'CScriptEngine::~CScriptEngine() {\n', b'CScriptEngine::~CScriptEngine() {\n\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n')],
        ),
        "CObjectHandler.h": (
            "92c87a9cb388bf4b3a1e5172d9a871558870fd5ae73e3ea921c2b7179fd41438",
            "57294ba4bbb600ba2db20780a4b9ab784d6e54fad2edb6c3b42706c5645ef7d0",
            [(b'\t\tCMapObject *object= _createObject ( type ) ;\n\t\tT casted=dynamic_cast<T> ( object );\n\t\tif ( casted==nullptr ) {\n\t\t\tdelete object;\n\t\t}\n\t\treturn casted;\n\t}\n\tvoid logProperties ( CMapObject *object ) const;\n\tconst QJsonObject *getObjectConfig() const;\nprivate:\n\tCMapObject *_createObject ( QString type ) const;\n', b'\t\tConstructible *object= _createObject ( type ) ;\n\t\tT casted=dynamic_cast<T> ( object );\n\t\tif ( casted==nullptr ) {\n\t\t\tdelete object;\n\t\t}\n\t\treturn casted;\n\t}\n\tvoid logProperties ( CMapObject *object ) const;\n\tconst QJsonObject *getObjectConfig() const;\nprivate:\n\tConstructible *_createObject ( QString type ) const;\n')],
        ),
        "CTypeHandler.cpp": (
            "b35e7e42020acd1997d2dff9b300bd653a318792dec0390bdb47933bf557bca9",
            "c1a3e23c65ba3b7bae3b12bfdbd1feec1a02765e8f6aad68e22838741b1942a6",
            [(b'\tobject = dynamic_cast<Constructible * > ( QMetaType::create ( typeId ) );\n', b'\tobject = dynamic_cast<Constructible *> ( static_cast<QObject *> ( QMetaType::create ( typeId ) ) );\n')],
        ),
        "CTile.h": (
            "2987720e206e6ab9c56817b78a06f0689a4386c134beaa8cf749c1a00507508a",
            "4d68da40372e472b73f623c966569d5253814c553e7be99182132d871b76c8e0",
            [(b'\tQ_PROPERTY ( bool objectType READ getObjectType WRITE setObjectType USER true )\npublic:\n\tCTile();\n\tCTile ( const CTile &tile );\n\tvirtual ~CTile();\n\tvirtual void onStep ( CCreature * );\n\tvoid move ( int x, int y, int z ) ;\n\tCoords getCoords();\n\tbool canStep() const;\n\tvoid setCanStep ( bool canStep );\n\tvoid addToScene ( CGameScene *scene );\n\tvoid removeFromScene ( CGameScene *scene );\n\n\tvirtual void setObjectName ( const QString &name );\n\tvirtual void setObjectType ( const QString &type );\n\n\tvirtual QString getObjectName() const override;\n\tvirtual QString getObjectType() const override;\nprivate:\n\tbool step=false;\n', b'\tQ_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )\npublic:\n    int posx=0, posy=0, posz=0;\n    CMap *getMap() const { return map; }\n    void setMap(CMap *value);\n    void moveTo(int x, int y, int z) { move(x - posx, y - posy, z - posz); }\n    void setVisible(bool visible) { QGraphicsPixmapItem::setVisible(visible); }\n    CTile();\n\tCTile ( const CTile &tile );\n\tvirtual ~CTile();\n\tvirtual void onStep ( CCreature * );\n\tvoid move ( int x, int y, int z ) ;\n\tCoords getCoords();\n\tbool canStep() const;\n\tvoid setCanStep ( bool canStep );\n\tvoid addToScene ( CGameScene *scene );\n\tvoid removeFromScene ( CGameScene *scene );\n\n\tvirtual void setObjectName ( const QString &name );\n\tvirtual void setObjectType ( const QString &type );\n\n\tvirtual QString getObjectName() const override;\n\tvirtual QString getObjectType() const override;\nprivate:\n\tbool step=false;\n    CMap *map=nullptr;\n')],
        ),
        "CTile.cpp": (
            "4fedbe248aa7cb00b5a2a78c6471f813013ee9e4d8de437c0742677a9f0ec9c1",
            "e2c6116c47141e8783edf9abe2119ab8b4e86adf87afe8c8094e28a76c5dfa83",
            [(b'\tscene->addItem ( this );\n\tsetXYZ (  posx , posy,posz );\n\tsetMap (  scene ->getMap() );\n}\n\nvoid CTile::removeFromScene ( CGameScene *scene ) {\n\tscene->removeItem ( this );\n}\n\nvoid CTile::setXYZ ( int x, int y, int z ) {\n\tposx = x;\n\tposy = y;\n\tposz = z;\n\tsetPos ( x*50,y*50 );\n}\n\nvoid CTile::setObjectName ( const QString &name ) {\n\tthis->QObject::setObjectName ( name );\n}\n\nvoid CTile::setObjectType ( const QString &type ) {\n\tthis->objectType=type;\n}\n\nQString CTile::getObjectName() const {\n\treturn this->QObject::objectName();\n}\n\nQString CTile::getObjectType() const {\n\treturn this->objectType;\n', b'\tscene->addItem ( toGraphicsItem() );\n\tsetXYZ (  posx , posy,posz );\n\tsetMap (  scene ->getMap() );\n}\n\nvoid CTile::removeFromScene ( CGameScene *scene ) {\n\tscene->removeItem ( toGraphicsItem() );\n}\n\nvoid CTile::setXYZ ( int x, int y, int z ) {\n\tposx = x;\n\tposy = y;\n\tposz = z;\n\tsetPos ( x*50,y*50 );\n}\n\nvoid CTile::setObjectName ( const QString &name ) {\n\tthis->QObject::setObjectName ( name );\n}\n\nvoid CTile::setObjectType ( const QString &type ) {\n\tthis->objectType=type;\n}\n\nQString CTile::getObjectName() const {\n\treturn this->QObject::objectName();\n}\n\nQString CTile::getObjectType() const {\n\treturn this->objectType;\n}\n\nvoid CTile::setMap(CMap *value) {\n    if (!value) return;\n    map = value;\n    if (scene() != map->getScene()) map->getScene()->addItem(toGraphicsItem());\n')],
        ),
    },
    "a64e71fc174103f81e7f3ef44ab8a79a312ea18b": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "d71895c9b668ad3b616bbeb81995b24fd01b3b24ccda8ad518ca27a27f16ddb6",
            "ac6bb906f168c4265ac4cbed6c9c8782ce316a3b80a9eaee198fcc067ba6343c",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'CScriptEngine::~CScriptEngine() {\n', b'CScriptEngine::~CScriptEngine() {\n\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n')],
        ),
        "CTypeHandler.cpp": (
            "e3eb28c3ea1ddf149f03e041d405a616de2ef738347a472443c3f6decc0d7aba",
            "d31d3481e6a37113f7a810942caa069714ea6295c460dc099e986bcd5713d356",
            [(b'    object = dynamic_cast<Constructible*>((Constructible*)raw);\n', b'    object = dynamic_cast<Constructible*>(static_cast<QObject*>(raw));\n')],
        ),
        "CTile.h": (
            "35d8654e774ddafc1e60f34b2a5e1ffd9b3df53fc153eed20224e11d06606683",
            "af7138a1ea192a2e1b7f487b6dee93cffbe0f914d748aee79ecc4629d7b75e3d",
            [(b'\tQ_PROPERTY ( bool canStep READ canStep WRITE setCanStep USER true )\n    Q_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )\npublic:\n\tCTile();\n\tCTile ( const CTile &tile );\n\tvirtual void onStep ( CCreature * );\n\tvoid move ( int x, int y, int z ) ;\n    void moveTo(int x,int y,int z);\n\tCoords getCoords();\n\tbool canStep() const;\n\tvoid setCanStep ( bool canStep );\n', b'\tfriend class CMap;\n\tQ_PROPERTY ( bool canStep READ canStep WRITE setCanStep USER true )\n    Q_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )\npublic:\n\tCTile();\n\tCTile ( const CTile &tile );\n\tvirtual void onStep ( CCreature * );\n\tvoid move ( int x, int y, int z ) ;\n    void moveTo(int x,int y,int z);\n\tCoords getCoords();\n\tbool canStep() const;\n\tvoid setCanStep ( bool canStep );\n\tvoid setVisible(bool visible) { QGraphicsPixmapItem::setVisible(visible); }\n')],
        ),
        "CTile.cpp": (
            "6ad0aa23fbb69e4be79ea407bb57c20d95d26970861c0c4b3b7f5cfbd7ffdb71",
            "6f72cdd422245b7c1e6395191f3c30dfb496ef56654e5b2300d83c39fa6d9400",
            [(b'    map = value;\n', b'    if (!value) return;\n    map = value;\n    if (scene() != map->getScene()) map->getScene()->addItem(toGraphicsItem());\n')],
        ),
    },
    "ead6e0b8498679734b6a4d05b88884a810527fed": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "d71895c9b668ad3b616bbeb81995b24fd01b3b24ccda8ad518ca27a27f16ddb6",
            "ac6bb906f168c4265ac4cbed6c9c8782ce316a3b80a9eaee198fcc067ba6343c",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'CScriptEngine::~CScriptEngine() {\n', b'CScriptEngine::~CScriptEngine() {\n\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n')],
        ),
    },
}
COMMITS = tuple(PROFILES)
PURPOSE = "Preserve map and Python lifetimes and repair the split tile factory interface"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown object factories revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Object factories source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Object factories input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Object factories output differs from the reviewed revision: {name}")
        pending[path] = updated
    for path, updated in pending.items():
        path.write_bytes(updated)


def identity(commit):
    return {
        "sourceCommit": commit,
        "files": {name: list(entry[:2]) for name, entry in PROFILES[commit].items()},
        "replaySha256": digest(Path(__file__).read_bytes()),
    }


def validate(commit, preparation):
    if commit not in COMMITS:
        raise ValueError("Unknown object factories revision")
    rows = [
        {
            "path": name,
            "before": {"kind": "file", "sha256": before},
            "after": {"kind": "file", "sha256": after},
            "purpose": PURPOSE,
        }
        for name, (before, after, _) in sorted(PROFILES[commit].items())
    ]
    actual = [row for row in preparation.get("outputs", []) if row.get("path") in PROFILES[commit]]
    if preparation.get("identity", {}).get("objectFactories") != identity(commit) or actual != rows:
        raise ValueError("Object factories evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["objectFactories"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
