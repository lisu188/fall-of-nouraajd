#include "core/CGlobal.h"
#include "CScripting.h"
#include "panel/CPanel.h"
#include "core/CGame.h"

using namespace boost::python;

BOOST_PYTHON_MODULE ( _core ) {
    class_<ModuleSpec, boost::noncopyable, std::shared_ptr<ModuleSpec>> ( "ModuleSpec", no_init )
            .add_property ( "loader", make_function ( &ModuleSpec::loader, return_internal_reference<>() ) )
            .def_readonly ( "name", &ModuleSpec::name )
            .def_readonly ( "submodule_search_locations", &ModuleSpec::subModuleSearch )
            .def_readonly ( "has_location", &ModuleSpec::hasLocation )
            .def_readonly ( "cached", &ModuleSpec::cached );
    class_<AScriptLoader, boost::noncopyable, std::shared_ptr<AScriptLoader>> ( "AScriptLoader", no_init )
            .def ( "exec_module", &AScriptLoader::exec_module )
            .def ( "find_spec", &AScriptLoader::find_spec, return_internal_reference<>() )
            .def ( "__eq__", &AScriptLoader::__eq__ );
    class_<CScriptLoader, bases<AScriptLoader>, boost::noncopyable, std::shared_ptr<CScriptLoader>> ( "CScriptLoader" );
    class_<CCustomScriptLoader, bases<AScriptLoader>, boost::noncopyable, std::shared_ptr<CCustomScriptLoader>> (
                "CCustomScriptLoader", no_init );
}

static int randint ( int i, int j ) { return rand() % ( j - i + 1 ) + i; }

#ifdef DEBUG_MODE
class CDebug {
public:
    static bool dump_path() {
        QApplication::instance()->setProperty ( "dump_path",!QApplication::instance()->property ( "dump_path" ).toBool() );
        return QApplication::instance()->property ( "dump_path" ).toBool() ;
    }
    static bool disable_pathfinder() {
        QApplication::instance()->setProperty ( "disable_pathfinder",!QApplication::instance()->property ( "disable_pathfinder" ).toBool() );
        return QApplication::instance()->property ( "disable_pathfinder" ).toBool() ;
    }
    static bool auto_save() {
        QApplication::instance()->setProperty ( "auto_save",!QApplication::instance()->property ( "auto_save" ).toBool() );
        return QApplication::instance()->property ( "auto_save" ).toBool() ;
    }
};

BOOST_PYTHON_MODULE ( debug ) {
    def ( "dump_path",CDebug::dump_path );
    def ( "disable_pathfinder",CDebug::disable_pathfinder );
    def ( "auto_save",CDebug::auto_save );
}
#endif

BOOST_PYTHON_MODULE ( _game ) {
    initialize_converters();
    def ( "randint", randint );
    class_<CGameObject, boost::noncopyable, std::shared_ptr<CGameObject>> ( "CGameObject", no_init )
            .def ( "getStringProperty", &CGameObject::getStringProperty )
            .def ( "getNumericProperty", &CGameObject::getNumericProperty )
            .def ( "getBoolProperty", &CGameObject::getBoolProperty )
            .def ( "setStringProperty", &CGameObject::setStringProperty )
            .def ( "setNumericProperty", &CGameObject::setNumericProperty )
            .def ( "setBoolProperty", &CGameObject::setBoolProperty )
            .def ( "getObjectProperty", &CGameObject::getObjectProperty<CGameObject> )
            .def ( "setObjectProperty", &CGameObject::setObjectProperty<CGameObject> )
            .def ( "incProperty", &CGameObject::incProperty );
    class_<Coords> ( "Coords", init<int, int, int>() )
    .def_readonly ( "x", &Coords::x )
    .def_readonly ( "y", &Coords::y )
    .def_readonly ( "z", &Coords::z );
    class_<CMap, boost::noncopyable, std::shared_ptr<CMap>> ( "CMap", no_init )
            .def ( "addObjectByName", &CMap::addObjectByName )
            .def ( "removeObjectByName", &CMap::removeObjectByName )
            .def ( "removeObject", &CMap::removeObject )
            .def ( "replaceTile", &CMap::replaceTile )
            .def ( "getPlayer", &CMap::getPlayer )
            .def ( "getLocationByName", &CMap::getLocationByName )
            .def ( "removeAll", &CMap::removeObjects )
            .def ( "getObjectHandler", &CMap::getObjectHandler )
            .def ( "getEventHandler", &CMap::getEventHandler )
            .def ( "addObject", &CMap::addObject )
            .def ( "createObject", &CMap::createObject<CGameObject> )
            .def ( "getGame", &CMap::getGame )
            .def ( "move", &CMap::move );
    void ( CObjectHandler::*registerType ) ( QString,
            std::function<std::shared_ptr<CGameObject>() > ) = &CObjectHandler::registerType;
    class_<CObjectHandler, boost::noncopyable, std::shared_ptr<CObjectHandler>> ( "CObjectHandler", no_init )
            .def ( "registerType", registerType );
    void ( CMapObject::*moveTo ) ( int, int, int ) = &CMapObject::moveTo;
    void ( CMapObject::*move ) ( int, int, int ) = &CMapObject::move;
    class_<CMapObject, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMapObject>> ( "CMapObject", no_init )
            .def ( "getMap", &CMapObject::getMap )
            .def ( "moveTo", moveTo )
            .def ( "move", move )
            .def ( "getCoords", &CMapObject::getCoords )
            .def ( "setCoords", &CMapObject::setCoords );
    class_<CEvent, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CEvent>> ( "CEventBase" );
    class_<CInteraction, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CInteraction>> ( "CInteraction" )
            .def ( "onAction", &CInteraction::onAction );
    class_<CEffect, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEffect>> ( "CEffectBase" )
            .def ( "getBonus", &CEffect::getBonus )
            .def ( "setBonus", &CEffect::setBonus )
            .def ( "getCaster", &CEffect::getCaster )
            .def ( "getVictim", &CEffect::getVictim )
            .def ( "getTimeLeft", &CEffect::getTimeLeft );
    class_<CEffectWrapper, bases<CEffect>, boost::noncopyable, std::shared_ptr<CEffectWrapper>> ( "CEffect" )
            .def ( "onEffect", &CEffectWrapper::onEffect );
    class_<CItem, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CItem>> ( "CItem" );
    class_<CWeapon, bases<CItem>, boost::noncopyable, std::shared_ptr<CWeapon>> ( "CWeapon" )
            .def ( "getInteraction", &CWeapon::getInteraction );
    class_<CBuilding, bases<CMapObject>, boost::noncopyable> ( "CBuildingBase" );
    void ( CCreature::*hurtInt ) ( int ) = &CCreature::hurt;
    void ( CCreature::*hurtFloat ) ( float ) = &CCreature::hurt;
    void ( CCreature::*hurtDmg ) ( std::shared_ptr<Damage> ) = &CCreature::hurt;
    class_<CCreature, bases<CMapObject>, boost::noncopyable, std::shared_ptr<CCreature>> ( "CCreature", no_init )
            .def ( "getDmg", &CCreature::getDmg )
            .def ( "hurt", hurtInt )
            .def ( "hurt", hurtDmg )
            .def ( "hurt", hurtFloat )
            .def ( "getWeapon", &CCreature::getWeapon )
            .def ( "getHpRatio", &CCreature::getHpRatio )
            .def ( "isAlive", &CCreature::isAlive )
            .def ( "getMana", &CCreature::getMana )
            .def ( "healProc", &CCreature::healProc )
            .def ( "heal", &CCreature::heal )
            .def ( "getHpMax", &CCreature::getHpMax )
            .def ( "getLevel", &CCreature::getLevel )
            .def ( "getStats", &CCreature::getStats )
            .def ( "addManaProc", &CCreature::addManaProc )
            .def ( "isPlayer", &CCreature::isPlayer )
            .def ( "trade", &CCreature::trade );
    class_<CPlayer, bases<CCreature>, boost::noncopyable, std::shared_ptr<CPlayer>> ( "CPlayer" )
            .def ( "addQuest", &CPlayer::addQuest );
    class_<CMonster, bases<CCreature>, boost::noncopyable, std::shared_ptr<CMonster>> ( "CMonster" );
    class_<CWrapper<CBuilding>, bases<CBuilding>, boost::noncopyable, std::shared_ptr<CWrapper<CBuilding>>> ( "CBuilding" )
    .def ( "onCreate", &CWrapper<CBuilding>::onCreate )
    .def ( "onTurn", &CWrapper<CBuilding>::onTurn )
    .def ( "onDestroy", &CWrapper<CBuilding>::onDestroy )
    .def ( "onLeave", &CWrapper<CBuilding>::onLeave )
    .def ( "onEnter", &CWrapper<CBuilding>::onEnter );
    class_<CWrapper<CEvent>, bases<CEvent>, boost::noncopyable, std::shared_ptr<CWrapper<CEvent>>> ( "CEvent" )
    .def ( "onCreate", &CWrapper<CEvent>::onCreate )
    .def ( "onTurn", &CWrapper<CEvent>::onTurn )
    .def ( "onLeave", &CWrapper<CEvent>::onLeave )
    .def ( "onDestroy", &CWrapper<CEvent>::onDestroy )
    .def ( "onEnter", &CWrapper<CEvent>::onEnter );
    class_<CInteractionWrapper, bases<CInteraction>, boost::noncopyable, std::shared_ptr<CInteractionWrapper> > (
        "CInteraction" )
    .def ( "performAction", &CInteractionWrapper::performAction )
    .def ( "configureEffect", &CInteractionWrapper::configureEffect );
    class_<Damage, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Damage>> ( "Damage" );
    class_<Stats, bases<CGameObject>, boost::noncopyable, std::shared_ptr<Stats>> ( "Stats" );
    class_<AGamePanel, boost::noncopyable, std::shared_ptr<AGamePanel>> ( "AGamePanel", no_init )
            .def ( "showPanel", &AGamePanel::showPanel );
    class_<CTextPanel, bases<AGamePanel>, boost::noncopyable, std::shared_ptr<CTextPanel>> ( "CTextPanel" );
    class_<CFightPanel, bases<AGamePanel>, boost::noncopyable, std::shared_ptr<CFightPanel>> ( "CFightPanel" );
    class_<CCharPanel, bases<AGamePanel>, boost::noncopyable, std::shared_ptr<CCharPanel>> ( "CCharPanel" );
    class_<CTradePanel, bases<AGamePanel>, boost::noncopyable, std::shared_ptr<CTradePanel>> ( "CTradePanel" );
    class_<CGuiHandler, boost::noncopyable, std::shared_ptr<CGuiHandler>> ( "CGuiHandler", no_init )
            .def ( "showMessage", &CGuiHandler::showMessage )
            .def ( "showPanel", &CGuiHandler::showPanel )
            .def ( "hidePanel", &CGuiHandler::hidePanel )
            .def ( "flipPanel", &CGuiHandler::flipPanel );
    class_<CTile, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTile>> ( "CTileBase" );
    class_<CTileWrapper, bases<CTile>, boost::noncopyable, std::shared_ptr<CTileWrapper> > ( "CTile" ).
    def ( "onStep", &CTileWrapper::onStep );
    class_<CPotion, bases<CItem>, boost::noncopyable, std::shared_ptr<CPotion>> ( "CPotionBase" );
    class_<CPotionWrapper, bases<CPotion>, boost::noncopyable, std::shared_ptr<CPotionWrapper> > ( "CPotion" ).
    def ( "onUse", &CPotionWrapper::onUse );
    class_<CGameEvent, boost::noncopyable, std::shared_ptr<CGameEvent>> ( "CGameEvent", no_init );
    class_<CGameEventCaused, bases<CGameEvent>, boost::noncopyable, std::shared_ptr<CGameEventCaused>> (
                "CGameEventCaused", no_init )
            .def ( "getCause", &CGameEventCaused::getCause );
    class_<CTrigger, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CTrigger>> ( "CTriggerBase", no_init );
    class_<CTriggerWrapper, bases<CTrigger>, boost::noncopyable, std::shared_ptr<CTriggerWrapper>> ( "CTrigger" )
            .def ( "trigger", &CTriggerWrapper::trigger );
    class_<CQuest, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CQuest>> ( "CQuestBase", no_init );
    class_<CQuestWrapper, bases<CQuest>, boost::noncopyable, std::shared_ptr<CQuestWrapper>> ( "CQuest" )
            .def ( "isCompleted", &CQuestWrapper::isCompleted )
            .def ( "onComplete", &CQuestWrapper::onComplete );
    class_<CEventHandler, boost::noncopyable, std::shared_ptr<CEventHandler>> ( "CEventHandler", no_init )
            .def ( "registerTrigger", &CEventHandler::registerTrigger );
    class_<CGame, boost::noncopyable, std::shared_ptr<CGame>> ( "CGame", no_init )
            .def ( "getMap", &CGame::getMap )
            .def ( "changeMap", &CGame::changeMap )
            .def ( "getGuiHandler", &CGame::getGuiHandler )
            .def ( "getObjectHandler", &CGame::getObjectHandler );
    class_<CMarket, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMarket> > ( "CMarket" );
}
