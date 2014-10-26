"""Pinned Linux build repairs for the game object, panel and item event revisions."""

import hashlib
from pathlib import Path

PROFILES = {
    "8ccff81bf2bb22a0d526742eaef570653e47e63c": {
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
        "CMapObject.h": (
            "38f50725cc2d4c9a846484d1688313021e13d850e8d5f90b9644f39c5b83c6b4",
            "e9bc75294c2421cb1b11209342ffb485e08d8c076ee43019d59c7d9b82f5f3db",
            [(b'class CGameObject : public QObject {\n\tQ_OBJECT\n\tQ_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )\npublic:\n\tQString getObjectType() const ;\n\tvoid setObjectType ( const QString &value ) ;\n\n\tvirtual CMap* getMap() =0;\n\tvirtual void setMap ( CMap *map ) =0;\n\n\tQ_INVOKABLE void setProperty ( QString name,QVariant property ) {\n\t\tQByteArray byteArray = name.toUtf8();\n\t\tconst char* cString = byteArray.constData();\n\t\tthis->QObject::setProperty ( cString,property );\n\t}\n\tQ_INVOKABLE QVariant property ( QString name ) const {\n\t\tQByteArray byteArray = name.toUtf8();\n\t\tconst char* cString = byteArray.constData();\n\t\treturn this->QObject::property ( cString );\n\t}\n\tQ_INVOKABLE void setStringProperty ( QString name,QString value ) {\n\t\tthis->setProperty ( name, value ) ;\n\t}\n\tQ_INVOKABLE void setBoolProperty ( QString name,bool value ) {\n\t\tthis->setProperty ( name,value );\n\t}\n\tQ_INVOKABLE void setNumericProperty ( QString name,int value ) {\n\t\tthis->setProperty ( name,value );\n\t}\n\tQ_INVOKABLE QString getStringProperty ( QString name ) const {\n\t\treturn this->property ( name ).toString();\n\t}\n\tQ_INVOKABLE bool getBoolProperty ( QString name ) const {\n\t\treturn this->property ( name ).toBool();\n\t}\n\tQ_INVOKABLE int getNumericProperty ( QString name ) const {\n\t\treturn this->property ( name ).toInt();\n\t}\n\tQ_INVOKABLE void incProperty ( QString name,int value ) {\n\t\tthis->setNumericProperty ( name,this->getNumericProperty ( name )+value );\n\t}\n\n\tvirtual ~CGameObject() =0;\nprivate:\n\tQString objectType;\n};\n\nclass CMapObject : public CGameObject,public CAnimatedObject {\n', b'class CGameObject : public CAnimatedObject {\n\tQ_OBJECT\n\tQ_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )\npublic:\n\tQString getObjectType() const ;\n\tvoid setObjectType ( const QString &value ) ;\n\n\tvirtual CMap* getMap();\n\tvirtual void setMap ( CMap *map );\n\n\tQ_INVOKABLE void setProperty ( QString name,QVariant property ) {\n\t\tQByteArray byteArray = name.toUtf8();\n\t\tconst char* cString = byteArray.constData();\n\t\tthis->QObject::setProperty ( cString,property );\n\t}\n\tQ_INVOKABLE QVariant property ( QString name ) const {\n\t\tQByteArray byteArray = name.toUtf8();\n\t\tconst char* cString = byteArray.constData();\n\t\treturn this->QObject::property ( cString );\n\t}\n\tQ_INVOKABLE void setStringProperty ( QString name,QString value ) {\n\t\tthis->setProperty ( name, value ) ;\n\t}\n\tQ_INVOKABLE void setBoolProperty ( QString name,bool value ) {\n\t\tthis->setProperty ( name,value );\n\t}\n\tQ_INVOKABLE void setNumericProperty ( QString name,int value ) {\n\t\tthis->setProperty ( name,value );\n\t}\n\tQ_INVOKABLE QString getStringProperty ( QString name ) const {\n\t\treturn this->property ( name ).toString();\n\t}\n\tQ_INVOKABLE bool getBoolProperty ( QString name ) const {\n\t\treturn this->property ( name ).toBool();\n\t}\n\tQ_INVOKABLE int getNumericProperty ( QString name ) const {\n\t\treturn this->property ( name ).toInt();\n\t}\n\tQ_INVOKABLE void incProperty ( QString name,int value ) {\n\t\tthis->setNumericProperty ( name,this->getNumericProperty ( name )+value );\n\t}\n\n\tvirtual ~CGameObject() =0;\nprivate:\n\tCMap *map=nullptr;\n\tQString objectType;\n};\n\nclass CMapObject : public CGameObject {\n')],
        ),
        "CTile.h": (
            "7c3e73192190cd0171670b2133e9ed26f31aac07cfd5752efb204882806c0ade",
            "a4e3e86139732e8c3cf05378f2773f3b197e032187aa78861993e08b17fa2910",
            [(b'class CTile : public CGameObject,public CAnimatedObject {\n', b'class CTile : public CGameObject {\n')],
        ),
        "CTile.cpp": (
            "01e4eccf20b29e7f31361826561feec3218a3f55e3f291a90592c0f307921dc4",
            "e7a6319328b9c40a8cac5c78351e2a34a31d53daf9834bf74cedb9d4db9aee97",
            [(b'void CTile::setObjectName ( const QString &name ) {\n\tthis->QObject::setObjectName ( name );\n}\n\nvoid CTile::setObjectType ( const QString &type ) {\n\tthis->objectType=type;\n}\n\nQString CTile::getObjectName() const {\n\treturn this->QObject::objectName();\n}\n\nQString CTile::getObjectType() const {\n\treturn this->objectType;\n}\n', b'')],
        ),
        "CInteraction.h": (
            "b068fe93e30847bae4e4fc58a8b61bfe1e891d1d4b9b966a388d661b46c3e9cb",
            "f88b0a5687b57ecf0cf9b939f2e0d625199d714739739ab33e67a71a3b2e4e11",
            [(b'class CInteraction : public CGameObject,public CAnimatedObject {\n', b'class CInteraction : public CGameObject {\n')],
        ),
        "CTypeHandler.h": (
            "e01f40298e5f472777c3a420d390bc65a7b1a9bff7181a5295e303a763d05602",
            "3b0cb0650bbed8b9506aac9fa0759d84c214d1ee93f2f46fb14a02b4a4473d07",
            [(b'class Constructible;\n', b'class CGameObject;\n')],
        ),
        "CTypeHandler.cpp": (
            "a44c66e5dcd7bcafc7c1b1f655638cbf98b003236ce93ab8800c2686a359a007",
            "af943b5c62fd2dc1ae2ccb1dff20cc5953fd72f204008c9a3d687aa0ca7c870b",
            [(b'Constructible *ATypeHandler::create ( QString ) {\n', b'CGameObject *ATypeHandler::create ( QString ) {\n')],
        ),
    },
    "74594f17271a871a3241e60f19aaa8f5c587409e": {
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
    "cc9bd684ba8fd530ea8369e4f5bf248c43c9e139": {
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
    "61369722a47d404eddf30cd505d82066af4f9b6e": {
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
PURPOSE = "Preserve runtime lifetimes and reconcile the transitional common Qt object base"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown game objects revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Game objects source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Game objects input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Game objects output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown game objects revision")
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
    if preparation.get("identity", {}).get("gameObjects") != identity(commit) or actual != rows:
        raise ValueError("Game objects evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["gameObjects"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
