#include "gui/panel/CGameQuestPanel.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CStatsGraphicsObject.h"
#include "gui/panel/CGameTradePanel.h"
#include "core/CTypes.h"
#include "core/CController.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/CTextureCache.h"

extern void add_member(std::shared_ptr<Value> object, std::string key, std::string value);

extern void add_member(std::shared_ptr<Value> object, std::string key, std::shared_ptr<Value> value);

extern void add_member(std::shared_ptr<Value> object, std::string key, bool value);

extern void add_member(std::shared_ptr<Value> object, std::string key, int value);

extern void add_arr_member(std::shared_ptr<Value> object, std::string value);

extern void add_arr_member(std::shared_ptr<Value> object, std::shared_ptr<Value> value);

extern void add_arr_member(std::shared_ptr<Value> object, bool value);

extern void add_arr_member(std::shared_ptr<Value> object, int value);


namespace {
    struct register_types4 {
        register_types4() {
            CTypes::register_type<CGameObject>();
            {
                CTypes::register_type<CGameGraphicsObject, CGameObject>();
                {
                    CTypes::register_type<CMapGraphicsObject, CGameGraphicsObject, CGameObject>();
                    CTypes::register_type<CStatsGraphicsObject, CGameGraphicsObject, CGameObject>();

                    CTypes::register_type<CGamePanel, CGameGraphicsObject, CGameObject>();
                    {
                        CTypes::register_type<CGameTextPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameInventoryPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameTradePanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameFightPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameQuestPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CGameCharacterPanel, CGamePanel, CGameGraphicsObject, CGameObject>();
                    }
                    CTypes::register_type<CAnimation, CGameGraphicsObject, CGameObject>();
                    {
                        CTypes::register_type<CStaticAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
                        CTypes::register_type<CDynamicAnimation, CAnimation, CGameGraphicsObject, CGameObject>();
                    }
                }
            }
        }
    } _register_types4;
}