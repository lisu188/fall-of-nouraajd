"""Pinned Linux build repairs for the handler, folder and configuration transitions."""

import hashlib
from pathlib import Path

PROFILES = {
    "35b69687549d2b68864d26b1711931835b819670": {
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
    "a97769c921cf57d945ffc10f70fd940ac86f3774": {
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
    "d732bf46e0b8a059330fdcbf4619ee7caf1c8381": {
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
    "8998701baa7ee3659346922c4dc2f143d619eeb1": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "8c8843f9c20aa4c712287f665be95053c37b8e91095403aa6afca979cecdf0f9",
            "25dc52e59724b02747acdbb7f7d680bc501a5982081d1b53406a3d988fa8a1da",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'CScriptEngine::~CScriptEngine() {\n', b'CScriptEngine::~CScriptEngine() {\n\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n')],
        ),
        "CResourcesHandler.h": (
            "8dc5c05cf18fce641ecd2861b09be4698e5320773c94b9d8c4300c6b615c49fe",
            "7d255cbf2dda61e262c05896912682a276f72d20fdc8fe5bc55750a9bb3e5ec9",
            [(b'#pragma once\r\n#include <QObject>\r\n#include <QFile>\r\n#include <QSet>\r\n#include <QString>\r\n\r\n', b'#pragma once\r\n#include <QObject>\r\n#include <QFile>\r\n#include <QSet>\r\n#include <QString>\r\n\r\n\n#include "handler/CHandler.h"\n')],
        ),
        "CTypeHandler.h": (
            "b3adf106d95b8934f690943f2921308b90be5b766c4c8ba250c792de56400201",
            "cb5929275d85c5ed5a33da485a5353558bdd6f654448c609a79726c8d3449102",
            [(b'#pragma once\n', b'#pragma once\n\n#include "handler/CHandler.h"\n')],
        ),
        "CGuiHandler.h": (
            "f9ebe0575fd003e012a3de929ee3c19891f2af35372745a4c48fbcd14103ccc9",
            "98b586071db06a9981f87bfb98f98c23839725a164999b9e7d03b14a68bbee52",
            [(b'class AGamePanel;\n', b'class AGamePanel;\n\n#include "handler/CHandler.h"\n')],
        ),
        "panel/CCharPanel.cpp": (
            "ca6e05ce586c606bc05cd492466f3f999c6d84f346f049e02ec7f23137485f2d",
            "d0c87899580f638ad1dbce2ec763cacd57226efdb8391712cd4375c16940cea8",
            [(b'\tplayerInventoryView = new CPlayerInventoryrView ( view );\n\tplayerInventoryView->setZValue ( 3 );\n\tplayerInventoryView->setParentItem ( this );\n\tplayerInventoryView->setAcceptDrops ( true );\n\tview->getScene()->addItem ( playerInventoryView );\n\tplayerEquippedView = new CPlayerEquippedView ( view );\n\tplayerEquippedView->setZValue ( 3 );\n\tplayerEquippedView->setParentItem ( this );\n\tview->getScene()->addItem ( playerEquippedView );\n\tbackpack=new BackPackObject ( view ,this );\n\tbackpack->show();\n}\n\nvoid CCharPanel::update() {\n', b'    if (!backpack) {\n        backpack = new BackPackObject(view, this);\n        backpack->show();\n    }\n    if (playerInventoryView || !view->getScene()->getPlayer()) return;\n\tplayerInventoryView = new CPlayerInventoryrView ( view );\n\tplayerInventoryView->setZValue ( 3 );\n\tplayerInventoryView->setParentItem ( this );\n\tplayerInventoryView->setAcceptDrops ( true );\n\tview->getScene()->addItem ( playerInventoryView );\n\tplayerEquippedView = new CPlayerEquippedView ( view );\n\tplayerEquippedView->setZValue ( 3 );\n\tplayerEquippedView->setParentItem ( this );\n\tview->getScene()->addItem ( playerEquippedView );\n}\n\nvoid CCharPanel::update() {\n    setUpPanel(view);\n    if (!playerInventoryView) return;\n')],
        ),
    },
    "ee6512a07829eaf651364996d604b043bfcdee8f": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "3ca3c73492c3b3853e63a009722678610882fd7a5ae7a792a39b5a2d7c875ddf",
            "6f8f4c590ed8709e2059498b09759af5f91b53e5b9b35071a287f928e8c8d9be",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "6ebd16f042ccb9e36ac801c9954cc061322911e85478eb064fbf6b91c8186be7",
            "28abf1907d3bb5ee311a0b5304e9861f67df712557115479358a9d5810d3438d",
            [(b'CScriptEngine::~CScriptEngine() {\n', b'CScriptEngine::~CScriptEngine() {\n\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n')],
        ),
        "CResourcesHandler.h": (
            "8dc5c05cf18fce641ecd2861b09be4698e5320773c94b9d8c4300c6b615c49fe",
            "7d255cbf2dda61e262c05896912682a276f72d20fdc8fe5bc55750a9bb3e5ec9",
            [(b'#pragma once\r\n#include <QObject>\r\n#include <QFile>\r\n#include <QSet>\r\n#include <QString>\r\n\r\n', b'#pragma once\r\n#include <QObject>\r\n#include <QFile>\r\n#include <QSet>\r\n#include <QString>\r\n\r\n\n#include "handler/CHandler.h"\n')],
        ),
        "CTypeHandler.h": (
            "b3adf106d95b8934f690943f2921308b90be5b766c4c8ba250c792de56400201",
            "cb5929275d85c5ed5a33da485a5353558bdd6f654448c609a79726c8d3449102",
            [(b'#pragma once\n', b'#pragma once\n\n#include "handler/CHandler.h"\n')],
        ),
        "CGuiHandler.h": (
            "f9ebe0575fd003e012a3de929ee3c19891f2af35372745a4c48fbcd14103ccc9",
            "98b586071db06a9981f87bfb98f98c23839725a164999b9e7d03b14a68bbee52",
            [(b'class AGamePanel;\n', b'class AGamePanel;\n\n#include "handler/CHandler.h"\n')],
        ),
        "panel/CCharPanel.cpp": (
            "ca6e05ce586c606bc05cd492466f3f999c6d84f346f049e02ec7f23137485f2d",
            "d0c87899580f638ad1dbce2ec763cacd57226efdb8391712cd4375c16940cea8",
            [(b'\tplayerInventoryView = new CPlayerInventoryrView ( view );\n\tplayerInventoryView->setZValue ( 3 );\n\tplayerInventoryView->setParentItem ( this );\n\tplayerInventoryView->setAcceptDrops ( true );\n\tview->getScene()->addItem ( playerInventoryView );\n\tplayerEquippedView = new CPlayerEquippedView ( view );\n\tplayerEquippedView->setZValue ( 3 );\n\tplayerEquippedView->setParentItem ( this );\n\tview->getScene()->addItem ( playerEquippedView );\n\tbackpack=new BackPackObject ( view ,this );\n\tbackpack->show();\n}\n\nvoid CCharPanel::update() {\n', b'    if (!backpack) {\n        backpack = new BackPackObject(view, this);\n        backpack->show();\n    }\n    if (playerInventoryView || !view->getScene()->getPlayer()) return;\n\tplayerInventoryView = new CPlayerInventoryrView ( view );\n\tplayerInventoryView->setZValue ( 3 );\n\tplayerInventoryView->setParentItem ( this );\n\tplayerInventoryView->setAcceptDrops ( true );\n\tview->getScene()->addItem ( playerInventoryView );\n\tplayerEquippedView = new CPlayerEquippedView ( view );\n\tplayerEquippedView->setZValue ( 3 );\n\tplayerEquippedView->setParentItem ( this );\n\tview->getScene()->addItem ( playerEquippedView );\n}\n\nvoid CCharPanel::update() {\n    setUpPanel(view);\n    if (!playerInventoryView) return;\n')],
        ),
    },
    "1e91cc7c3b84d79b6442e341453d729bfa4af802": {
        "handler/CTypeHandler.cpp": (
            "91c1598943e7c353e21cca66398e7d4dee3e76d7d28ecd8fb82cd1f2f3978c89",
            "e61d72e4024e8a3eb242a40c78d064e27e7bb310d1d31743e512ea86b27b214f",
            [(b'CGameObject *PyTypeHandler::create ( QString name ) {\n', b'CGameObject *PyTypeHandler::create ( QString name ) {\n\tif (name.startsWith(".")) name.prepend("game");\n')],
        ),
        "scripts/game/__init__.py": (
            "aa6c7734dd7f8977f9654c1581ee33b9199033da5ce1145298a6d279ec520283",
            "4c68be44d6d0fc771361bf8c9f2c45d29e7b9aa677ad5b855f3c54956df7f651",
            [(b'from . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n', b'\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n\nfrom . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n')],
        ),
        "config/weapons.json": (
            "38c8c8ff0f7716c9f91ff74f57fed247588c44a6abb52c1277f3e6211e83bb89",
            "779dbfda47308db6bdd052e459011da176549df6e92a124f7e5a1c03fcf23980",
            [(b'    "BeachTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/beach",\n            "canStep": true\n        }\n    },\n    "DesertTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/desert",\n            "canStep": true\n        }\n    },\n    "GrassTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/grass",\n            "canStep": true\n        }\n    },\n    "GroundTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/ground",\n            "canStep": true\n        }\n    },\n    "LavaTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/lava",\n            "canStep": true\n        }\n    },\n    "MountainTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/mountain",\n            "canStep": false\n        }\n    },\n    "RoadTile": {\n        "class": "RoadTile",\n        "properties": {\n            "animation": "images/tiles/road",\n            "canStep": true\n        }\n    },\n    "SnowTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/snow",\n            "canStep": true\n        }\n    },\n    "SwampTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/swamp",\n            "canStep": true\n        }\n    },\n    "WastelandTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/wasteland",\n            "canStep": true\n        }\n    },\n    "WaterTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/water",\n            "canStep": false\n', b'    "BladeOfDarkDreams": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/bladeofdarkdreams",\n            "bonus": {\n                "agility": 7,\n                "crit": 3,\n                "dmgMax": 42,\n                "dmgMin": 35,\n                "intelligence": 5,\n                "stamina": 12,\n                "strength": 13\n            },\n            "power": 9\n        }\n    },\n    "BroadSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/broadsword",\n            "bonus": {\n                "agility": 2,\n                "dmgMax": 18,\n                "dmgMin": 15,\n                "intelligence": 1,\n                "stamina": 4,\n                "strength": 5\n            },\n            "power": 5\n        }\n    },\n    "ChaosSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/chaossword",\n            "bonus": {\n                "attack": 15,\n                "damage": 25\n            },\n            "interaction": "ChaosBlast",\n            "power": 18\n        }\n    },\n    "Dagger": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/dagger",\n            "bonus": {\n                "agility": 4,\n                "dmgMax": 11,\n                "dmgMin": 8,\n                "stamina": 2\n            },\n            "power": 3\n        }\n    },\n    "DaggerOfVileHeart": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/daggerofvileheart",\n            "bonus": {\n                "agility": 15,\n                "crit": 6,\n                "dmgMax": 37,\n                "dmgMin": 33,\n                "intelligence": 8,\n                "stamina": 11,\n                "strength": 5\n            },\n            "power": 9\n        }\n    },\n    "Knife": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/knife",\n            "bonus": {\n                "agility": 1,\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "stamina": 1\n            }\n        }\n    },\n    "LongSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/longsword",\n            "bonus": {\n                "dmgMax": 14,\n                "dmgMin": 12,\n                "stamina": 2,\n                "strength": 1\n            },\n            "power": 3\n        }\n    },\n    "ShadowBlade": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shadowblade",\n            "bonus": {\n                "agility": 18,\n                "crit": 6,\n                "dmgMax": 60,\n                "dmgMin": 54,\n                "intelligence": 17,\n                "stamina": 12,\n                "strength": 10\n            },\n            "power": 25\n        }\n    },\n    "ShortStaff": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shortstaff",\n            "bonus": {\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "intelligence": 1,\n                "stamina": 1\n            }\n        }\n    },\n    "ShortSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shortsword",\n            "bonus": {\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "stamina": 1,\n                "strength": 1\n            }\n        }\n    },\n    "Staff": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/staff",\n            "bonus": {\n                "dmgMax": 10,\n                "dmgMin": 7,\n                "intelligence": 5,\n                "stamina": 2\n            },\n            "interaction": "ElemStaff",\n            "power": 3\n        }\n    },\n    "StaffOfTheAbyss": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/staffoftheabyss",\n            "bonus": {\n                "agility": 10,\n                "dmgMax": 41,\n                "dmgMin": 34,\n                "intelligence": 12,\n                "stamina": 8,\n                "strength": 4\n            },\n            "power": 9\n        }\n    },\n    "Stiletto": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/stiletto",\n            "bonus": {\n                "agility": 4,\n                "dmgMax": 17,\n                "dmgMin": 14,\n                "intelligence": 0,\n                "stamina": 5,\n                "strength": 3\n            },\n            "power": 5\n        }\n    },\n    "Sword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/sword",\n            "bonus": {\n                "attack": 5,\n                "damage": 10\n            }\n        }\n    },\n    "Valkyrie": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/valkyrie",\n            "bonus": {\n                "agility": 17,\n                "crit": 1,\n                "dmgMax": 59,\n                "dmgMin": 52,\n                "intelligence": 20,\n                "stamina": 14,\n                "strength": 8\n            },\n            "power": 25\n        }\n    },\n    "Void": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/void",\n            "bonus": {\n                "agility": 12,\n                "block": 4,\n                "crit": 3,\n                "dmgMax": 65,\n                "dmgMin": 62,\n                "intelligence": 8,\n                "stamina": 17,\n                "strength": 15\n            },\n            "power": 25\n        }\n    },\n    "Wand": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/wand",\n            "bonus": {\n                "agility": 2,\n                "dmgMax": 17,\n                "dmgMin": 13,\n                "intelligence": 7,\n                "stamina": 2,\n                "strength": 1\n            },\n            "power": 5\n')],
        ),
    },
    "225fe55433f89e7714c1363ac89712f7fa0560b3": {
        "handler/CTypeHandler.cpp": (
            "91c1598943e7c353e21cca66398e7d4dee3e76d7d28ecd8fb82cd1f2f3978c89",
            "e61d72e4024e8a3eb242a40c78d064e27e7bb310d1d31743e512ea86b27b214f",
            [(b'CGameObject *PyTypeHandler::create ( QString name ) {\n', b'CGameObject *PyTypeHandler::create ( QString name ) {\n\tif (name.startsWith(".")) name.prepend("game");\n')],
        ),
        "scripts/game/__init__.py": (
            "aa6c7734dd7f8977f9654c1581ee33b9199033da5ce1145298a6d279ec520283",
            "4c68be44d6d0fc771361bf8c9f2c45d29e7b9aa677ad5b855f3c54956df7f651",
            [(b'from . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n', b'\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n\nfrom . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n')],
        ),
        "config/weapons.json": (
            "38c8c8ff0f7716c9f91ff74f57fed247588c44a6abb52c1277f3e6211e83bb89",
            "779dbfda47308db6bdd052e459011da176549df6e92a124f7e5a1c03fcf23980",
            [(b'    "BeachTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/beach",\n            "canStep": true\n        }\n    },\n    "DesertTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/desert",\n            "canStep": true\n        }\n    },\n    "GrassTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/grass",\n            "canStep": true\n        }\n    },\n    "GroundTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/ground",\n            "canStep": true\n        }\n    },\n    "LavaTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/lava",\n            "canStep": true\n        }\n    },\n    "MountainTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/mountain",\n            "canStep": false\n        }\n    },\n    "RoadTile": {\n        "class": "RoadTile",\n        "properties": {\n            "animation": "images/tiles/road",\n            "canStep": true\n        }\n    },\n    "SnowTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/snow",\n            "canStep": true\n        }\n    },\n    "SwampTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/swamp",\n            "canStep": true\n        }\n    },\n    "WastelandTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/wasteland",\n            "canStep": true\n        }\n    },\n    "WaterTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/water",\n            "canStep": false\n', b'    "BladeOfDarkDreams": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/bladeofdarkdreams",\n            "bonus": {\n                "agility": 7,\n                "crit": 3,\n                "dmgMax": 42,\n                "dmgMin": 35,\n                "intelligence": 5,\n                "stamina": 12,\n                "strength": 13\n            },\n            "power": 9\n        }\n    },\n    "BroadSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/broadsword",\n            "bonus": {\n                "agility": 2,\n                "dmgMax": 18,\n                "dmgMin": 15,\n                "intelligence": 1,\n                "stamina": 4,\n                "strength": 5\n            },\n            "power": 5\n        }\n    },\n    "ChaosSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/chaossword",\n            "bonus": {\n                "attack": 15,\n                "damage": 25\n            },\n            "interaction": "ChaosBlast",\n            "power": 18\n        }\n    },\n    "Dagger": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/dagger",\n            "bonus": {\n                "agility": 4,\n                "dmgMax": 11,\n                "dmgMin": 8,\n                "stamina": 2\n            },\n            "power": 3\n        }\n    },\n    "DaggerOfVileHeart": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/daggerofvileheart",\n            "bonus": {\n                "agility": 15,\n                "crit": 6,\n                "dmgMax": 37,\n                "dmgMin": 33,\n                "intelligence": 8,\n                "stamina": 11,\n                "strength": 5\n            },\n            "power": 9\n        }\n    },\n    "Knife": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/knife",\n            "bonus": {\n                "agility": 1,\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "stamina": 1\n            }\n        }\n    },\n    "LongSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/longsword",\n            "bonus": {\n                "dmgMax": 14,\n                "dmgMin": 12,\n                "stamina": 2,\n                "strength": 1\n            },\n            "power": 3\n        }\n    },\n    "ShadowBlade": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shadowblade",\n            "bonus": {\n                "agility": 18,\n                "crit": 6,\n                "dmgMax": 60,\n                "dmgMin": 54,\n                "intelligence": 17,\n                "stamina": 12,\n                "strength": 10\n            },\n            "power": 25\n        }\n    },\n    "ShortStaff": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shortstaff",\n            "bonus": {\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "intelligence": 1,\n                "stamina": 1\n            }\n        }\n    },\n    "ShortSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shortsword",\n            "bonus": {\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "stamina": 1,\n                "strength": 1\n            }\n        }\n    },\n    "Staff": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/staff",\n            "bonus": {\n                "dmgMax": 10,\n                "dmgMin": 7,\n                "intelligence": 5,\n                "stamina": 2\n            },\n            "interaction": "ElemStaff",\n            "power": 3\n        }\n    },\n    "StaffOfTheAbyss": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/staffoftheabyss",\n            "bonus": {\n                "agility": 10,\n                "dmgMax": 41,\n                "dmgMin": 34,\n                "intelligence": 12,\n                "stamina": 8,\n                "strength": 4\n            },\n            "power": 9\n        }\n    },\n    "Stiletto": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/stiletto",\n            "bonus": {\n                "agility": 4,\n                "dmgMax": 17,\n                "dmgMin": 14,\n                "intelligence": 0,\n                "stamina": 5,\n                "strength": 3\n            },\n            "power": 5\n        }\n    },\n    "Sword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/sword",\n            "bonus": {\n                "attack": 5,\n                "damage": 10\n            }\n        }\n    },\n    "Valkyrie": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/valkyrie",\n            "bonus": {\n                "agility": 17,\n                "crit": 1,\n                "dmgMax": 59,\n                "dmgMin": 52,\n                "intelligence": 20,\n                "stamina": 14,\n                "strength": 8\n            },\n            "power": 25\n        }\n    },\n    "Void": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/void",\n            "bonus": {\n                "agility": 12,\n                "block": 4,\n                "crit": 3,\n                "dmgMax": 65,\n                "dmgMin": 62,\n                "intelligence": 8,\n                "stamina": 17,\n                "strength": 15\n            },\n            "power": 25\n        }\n    },\n    "Wand": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/wand",\n            "bonus": {\n                "agility": 2,\n                "dmgMax": 17,\n                "dmgMin": 13,\n                "intelligence": 7,\n                "stamina": 2,\n                "strength": 1\n            },\n            "power": 5\n')],
        ),
    },
    "dc3f989ddf8cdcbf6af1302823c0ce653f546baa": {
        "handler/CTypeHandler.cpp": (
            "91c1598943e7c353e21cca66398e7d4dee3e76d7d28ecd8fb82cd1f2f3978c89",
            "e61d72e4024e8a3eb242a40c78d064e27e7bb310d1d31743e512ea86b27b214f",
            [(b'CGameObject *PyTypeHandler::create ( QString name ) {\n', b'CGameObject *PyTypeHandler::create ( QString name ) {\n\tif (name.startsWith(".")) name.prepend("game");\n')],
        ),
        "scripts/game/__init__.py": (
            "aa6c7734dd7f8977f9654c1581ee33b9199033da5ce1145298a6d279ec520283",
            "4c68be44d6d0fc771361bf8c9f2c45d29e7b9aa677ad5b855f3c54956df7f651",
            [(b'from . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n', b'\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n\nfrom . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n')],
        ),
        "config/weapons.json": (
            "38c8c8ff0f7716c9f91ff74f57fed247588c44a6abb52c1277f3e6211e83bb89",
            "779dbfda47308db6bdd052e459011da176549df6e92a124f7e5a1c03fcf23980",
            [(b'    "BeachTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/beach",\n            "canStep": true\n        }\n    },\n    "DesertTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/desert",\n            "canStep": true\n        }\n    },\n    "GrassTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/grass",\n            "canStep": true\n        }\n    },\n    "GroundTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/ground",\n            "canStep": true\n        }\n    },\n    "LavaTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/lava",\n            "canStep": true\n        }\n    },\n    "MountainTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/mountain",\n            "canStep": false\n        }\n    },\n    "RoadTile": {\n        "class": "RoadTile",\n        "properties": {\n            "animation": "images/tiles/road",\n            "canStep": true\n        }\n    },\n    "SnowTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/snow",\n            "canStep": true\n        }\n    },\n    "SwampTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/swamp",\n            "canStep": true\n        }\n    },\n    "WastelandTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/wasteland",\n            "canStep": true\n        }\n    },\n    "WaterTile": {\n        "class": "CTile",\n        "properties": {\n            "animation": "images/tiles/water",\n            "canStep": false\n', b'    "BladeOfDarkDreams": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/bladeofdarkdreams",\n            "bonus": {\n                "agility": 7,\n                "crit": 3,\n                "dmgMax": 42,\n                "dmgMin": 35,\n                "intelligence": 5,\n                "stamina": 12,\n                "strength": 13\n            },\n            "power": 9\n        }\n    },\n    "BroadSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/broadsword",\n            "bonus": {\n                "agility": 2,\n                "dmgMax": 18,\n                "dmgMin": 15,\n                "intelligence": 1,\n                "stamina": 4,\n                "strength": 5\n            },\n            "power": 5\n        }\n    },\n    "ChaosSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/chaossword",\n            "bonus": {\n                "attack": 15,\n                "damage": 25\n            },\n            "interaction": "ChaosBlast",\n            "power": 18\n        }\n    },\n    "Dagger": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/dagger",\n            "bonus": {\n                "agility": 4,\n                "dmgMax": 11,\n                "dmgMin": 8,\n                "stamina": 2\n            },\n            "power": 3\n        }\n    },\n    "DaggerOfVileHeart": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/daggerofvileheart",\n            "bonus": {\n                "agility": 15,\n                "crit": 6,\n                "dmgMax": 37,\n                "dmgMin": 33,\n                "intelligence": 8,\n                "stamina": 11,\n                "strength": 5\n            },\n            "power": 9\n        }\n    },\n    "Knife": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/knife",\n            "bonus": {\n                "agility": 1,\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "stamina": 1\n            }\n        }\n    },\n    "LongSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/longsword",\n            "bonus": {\n                "dmgMax": 14,\n                "dmgMin": 12,\n                "stamina": 2,\n                "strength": 1\n            },\n            "power": 3\n        }\n    },\n    "ShadowBlade": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shadowblade",\n            "bonus": {\n                "agility": 18,\n                "crit": 6,\n                "dmgMax": 60,\n                "dmgMin": 54,\n                "intelligence": 17,\n                "stamina": 12,\n                "strength": 10\n            },\n            "power": 25\n        }\n    },\n    "ShortStaff": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shortstaff",\n            "bonus": {\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "intelligence": 1,\n                "stamina": 1\n            }\n        }\n    },\n    "ShortSword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/shortsword",\n            "bonus": {\n                "dmgMax": 7,\n                "dmgMin": 5,\n                "stamina": 1,\n                "strength": 1\n            }\n        }\n    },\n    "Staff": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/staff",\n            "bonus": {\n                "dmgMax": 10,\n                "dmgMin": 7,\n                "intelligence": 5,\n                "stamina": 2\n            },\n            "interaction": "ElemStaff",\n            "power": 3\n        }\n    },\n    "StaffOfTheAbyss": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/staffoftheabyss",\n            "bonus": {\n                "agility": 10,\n                "dmgMax": 41,\n                "dmgMin": 34,\n                "intelligence": 12,\n                "stamina": 8,\n                "strength": 4\n            },\n            "power": 9\n        }\n    },\n    "Stiletto": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/stiletto",\n            "bonus": {\n                "agility": 4,\n                "dmgMax": 17,\n                "dmgMin": 14,\n                "intelligence": 0,\n                "stamina": 5,\n                "strength": 3\n            },\n            "power": 5\n        }\n    },\n    "Sword": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/sword",\n            "bonus": {\n                "attack": 5,\n                "damage": 10\n            }\n        }\n    },\n    "Valkyrie": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/valkyrie",\n            "bonus": {\n                "agility": 17,\n                "crit": 1,\n                "dmgMax": 59,\n                "dmgMin": 52,\n                "intelligence": 20,\n                "stamina": 14,\n                "strength": 8\n            },\n            "power": 25\n        }\n    },\n    "Void": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/void",\n            "bonus": {\n                "agility": 12,\n                "block": 4,\n                "crit": 3,\n                "dmgMax": 65,\n                "dmgMin": 62,\n                "intelligence": 8,\n                "stamina": 17,\n                "strength": 15\n            },\n            "power": 25\n        }\n    },\n    "Wand": {\n        "class": "CWeapon",\n        "properties": {\n            "animation": "images/items/weapons/wand",\n            "bonus": {\n                "agility": 2,\n                "dmgMax": 17,\n                "dmgMin": 13,\n                "intelligence": 7,\n                "stamina": 2,\n                "strength": 1\n            },\n            "power": 5\n')],
        ),
    },
    "ddb05027fb3e831cbef7f16f1dea58f519c1756c": {
        "handler/CTypeHandler.cpp": (
            "91c1598943e7c353e21cca66398e7d4dee3e76d7d28ecd8fb82cd1f2f3978c89",
            "e61d72e4024e8a3eb242a40c78d064e27e7bb310d1d31743e512ea86b27b214f",
            [(b'CGameObject *PyTypeHandler::create ( QString name ) {\n', b'CGameObject *PyTypeHandler::create ( QString name ) {\n\tif (name.startsWith(".")) name.prepend("game");\n')],
        ),
        "scripts/game/__init__.py": (
            "aa6c7734dd7f8977f9654c1581ee33b9199033da5ce1145298a6d279ec520283",
            "4c68be44d6d0fc771361bf8c9f2c45d29e7b9aa677ad5b855f3c54956df7f651",
            [(b'from . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n', b'\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n\nfrom . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n')],
        ),
    },
    "70d0d690df45877698cb094405e25be00a8139fd": {
        "handler/CTypeHandler.cpp": (
            "91c1598943e7c353e21cca66398e7d4dee3e76d7d28ecd8fb82cd1f2f3978c89",
            "e61d72e4024e8a3eb242a40c78d064e27e7bb310d1d31743e512ea86b27b214f",
            [(b'CGameObject *PyTypeHandler::create ( QString name ) {\n', b'CGameObject *PyTypeHandler::create ( QString name ) {\n\tif (name.startsWith(".")) name.prepend("game");\n')],
        ),
        "scripts/game/__init__.py": (
            "aa6c7734dd7f8977f9654c1581ee33b9199033da5ce1145298a6d279ec520283",
            "4c68be44d6d0fc771361bf8c9f2c45d29e7b9aa677ad5b855f3c54956df7f651",
            [(b'from . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n', b'\ndef switchClass(object,cls):\n    if cls and type(cls) != float:\n        object.__class__=cls\n\ndef game_object(object):\n    from _core import registerType\n    registerType(object.__name__,object)\n    return object\n\ndef game_trigger(event,object):\n    def trigger_wrapper(f):\n        pass\n    return trigger_wrapper\n\nfrom . import interaction\nfrom . import object\nfrom . import effect\nfrom . import tile\nfrom . import potion\n')],
        ),
    },
    "2d45bf477dde4ad9f196d3ba6e440dbeea7b4234": {
        "handler/CObjectHandler.cpp": (
            "00ad8ad3ae7df79512565d3c98abae17e4e13afa45353e54183012c395ef2066",
            "7cfcb1868f6a27b6cd2e6c462552a9eae35d5e4fb0e2ed08a0c7b1d110cecef3",
            [(b'\tCGameObject *object = CTypeHandler::create ( className );\n', b"\tCGameObject *object = CTypeHandler::create ( className.startsWith('.') ? className.section('.', -1) : className );\n")],
        ),
    },
}
COMMITS = tuple(PROFILES)
PURPOSE = "Preserve runtime lifetimes and reconcile the surviving folder, handler and configuration interfaces"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown historical handlers revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Historical handlers source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Historical handlers input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Historical handlers output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown historical handlers revision")
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
    if preparation.get("identity", {}).get("historicalHandlers") != identity(commit) or actual != rows:
        raise ValueError("Historical handlers evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["historicalHandlers"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
