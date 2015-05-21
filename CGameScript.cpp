#include "CGlobal.h"
#include "object/CObject.h"
#include "CUtil.h"
#include "CMap.h"
#include "panel/CPanel.h"
#include "handler/CHandler.h"
#include "CScriptLoader.h"
#include "CGame.h"

using namespace boost::python;

template<>
void CMap::removeAll ( object func ) {
    QList<CMapObject*> objects;
    for (  auto it :mapObjects ) {
        if ( func ( boost::ref ( it.second ) ) ) {
            objects.append ( it.second );
        }
    }
    for (  auto it :objects ) {
        removeObject ( it );
    }
}

struct QString_to_python_str {
    static PyObject* convert ( QString const& s ) {
        return boost::python::incref (
                   boost::python::object (
                       s.toLatin1().constData() ).ptr() );
    }
};

struct QString_from_python_str {
    QString_from_python_str() {
        boost::python::converter::registry::push_back (
            &convertible,
            &construct,
            boost::python::type_id<QString>() );
    }

    // Determine if obj_ptr can be converted in a QString
    static void* convertible ( PyObject* obj_ptr ) {
        if ( !        PyUnicode_Check ( obj_ptr ) ) { return 0; }
        return obj_ptr;
    }

    // Convert obj_ptr into a QString
    static void construct (
        PyObject* obj_ptr,
        boost::python::converter::rvalue_from_python_stage1_data* data ) {
        // Extract the character data from the python string
        const char* value = _PyUnicode_AsString ( obj_ptr );

        // Verify that obj_ptr is a string (should be ensured by convertible())
        assert ( value );

        // Grab pointer to memory into which to construct the new QString
        void* storage = (
                            ( boost::python::converter::rvalue_from_python_storage<QString>* )
                            data )->storage.bytes;

        // in-place construct the new QString using the character data
        // extraced from the python object
        new ( storage ) QString ( value );

        // Stash the memory chunk pointer for later use by boost.python
        data->convertible = storage;
    }
};

static void initializeConverters() {
    using namespace boost::python;

    // register the to-python converter
    to_python_converter<
    QString,
    QString_to_python_str>();

    // register the from-python converter
    QString_from_python_str();
}

template<class T>
class CWrapper :public T,public wrapper<CWrapper<T>> {
public:
    virtual void onEnter ( CGameEvent *event ) override final {
        if ( auto f=this->get_override ( "onEnter" ) ) {
            f ( boost::ref ( event ) );
        } else {
            this->T::onEnter ( event );
        }
    }
    virtual void onTurn ( CGameEvent *event )  override final {
        if ( auto f=this->get_override ( "onTurn" ) ) {
            f ( boost::ref ( event ) );
        } else {
            this->T::onTurn ( event );
        }
    }

    virtual void onCreate ( CGameEvent *event )  override final {
        if ( auto f=this->get_override ( "onCreate" ) ) {
            f ( boost::ref ( event ) );
        } else {
            this->T::onCreate ( event );
        }
    }
    virtual void onDestroy ( CGameEvent *event )  override final {
        if ( auto f=this->get_override ( "onDestroy" ) ) {
            f ( boost::ref ( event ) );
        } else {
            this->T::onDestroy ( event );
        }
    }
    virtual void onLeave ( CGameEvent *event )  override final {
        if ( auto f=this->get_override ( "onLeave" ) ) {
            f ( boost::ref ( event ) );
        } else {
            this->T::onLeave ( event );
        }
    }
};

class CInteractionWrapper :public CInteraction,public wrapper<CInteractionWrapper> {
public:
    virtual void performAction ( CCreature*first,CCreature*second )  override final {
        if ( auto f=this->get_override ( "performAction" ) ) {
            f ( boost::ref ( first ),boost::ref ( second ) );
        } else {
            this->CInteraction::performAction ( first,second );
        }
    }
    virtual bool configureEffect ( CEffect*effect )  override final {
        if ( auto f=this->get_override ( "configureEffect" ) ) {
            return f ( boost::ref ( effect ) );
        } else {
            return this->CInteraction::configureEffect ( effect );
        }
    }
};

class CEffectWrapper :public CEffect,public wrapper<CEffectWrapper> {
public:
    virtual bool onEffect()  override final {
        if ( auto f=this->get_override ( "onEffect" ) ) {
            return f ();
        } else {
            return this->CEffect::onEffect() ;
        }
    }
};

class CTileWrapper:public CTile,public wrapper<CTileWrapper> {
public:
    virtual void onStep ( CCreature * creature )  override final {
        if ( auto f=this->get_override ( "onStep" ) ) {
            f ( boost::ref ( creature ) );
        } else {
            this->CTile::onStep ( creature ) ;
        }
    }
};

class CPotionWrapper:public CPotion,public wrapper<CPotionWrapper> {
public:
    virtual void onUse ( CGameEvent * event )  override final {
        if ( auto f=this->get_override ( "onUse" ) ) {
            f ( boost::ref ( event ) );
        } else {
            this->CPotion::onUse ( event ) ;
        }
    }
};

class CTriggerWrapper:public CTrigger,public wrapper<CTriggerWrapper> {
public:
    virtual void trigger ( CGameObject *object,CGameEvent * event )  override final {
        if ( auto f=this->get_override ( "trigger" ) ) {
            f ( boost::ref ( object ) ,boost::ref ( event ) );
        } else {
            this->CTrigger::trigger ( object,event ) ;
        }
    }
};

class CQuestWrapper:public CQuest,public wrapper<CQuestWrapper> {
public:
    virtual bool isCompleted()  override final {
        if ( auto f=this->get_override ( "isCompleted" ) ) {
            return f();
        } else {
            return this->CQuest::isCompleted();
        }
    }
    virtual void onComplete() override final {
        if ( auto f=this->get_override ( "onComplete" ) ) {
            f();
        } else {
            this->CQuest::onComplete();
        }
    }
};

static void registerType ( QString name,object constructor ) {
    CTypeHandler::registerType ( name,[constructor] () -> CGameObject* {
        return extract<CGameObject*> ( incref ( constructor().ptr() ) );
    } );
}

BOOST_PYTHON_MODULE ( _core ) {
    class_<ModuleSpec,boost::noncopyable> ( "ModuleSpec",no_init )
    .add_property ( "loader",make_function ( &ModuleSpec::loader ,return_internal_reference<>() ) )
    .def_readonly ( "name",&ModuleSpec::name )
    .def_readonly ( "submodule_search_locations",&ModuleSpec::subModuleSearch )
    .def_readonly ( "has_location",&ModuleSpec::hasLocation )
    .def_readonly ( "cached",&ModuleSpec::cached );
    class_<AScriptLoader,boost::noncopyable> ( "AScriptLoader" ,no_init )
    .def ( "exec_module",&AScriptLoader::exec_module )
    .def ( "find_spec",&AScriptLoader::find_spec ,return_internal_reference<>() )
    .def ( "__eq__",&AScriptLoader::__eq__ );
    class_<CScriptLoader,bases<AScriptLoader>,boost::noncopyable> ( "CScriptLoader" );
    class_<CCustomScriptLoader,bases<AScriptLoader>,boost::noncopyable> ( "CCustomScriptLoader",no_init );
    def ( "registerType",registerType );
}

static int randint ( int i,int j ) {
    return rand() % ( j-i+1 )+i;
}

BOOST_PYTHON_MODULE ( _game ) {
    initializeConverters();
    def ( "randint",randint );
    class_<CGameObject,boost::noncopyable> ( "CGameObject",no_init )
    PY_PROPERTY_ACCESSOR ( CGameObject );
    class_<Coords> ( "Coords",init<int,int,int>() )
    .def_readonly ( "x",&Coords::x )
    .def_readonly ( "y",&Coords::y )
    .def_readonly ( "z",&Coords::z );
    class_<CMap,boost::noncopyable> ( "CMap",no_init )
    .def ( "addObjectByName",&CMap::addObjectByName )
    .def ( "removeObjectByName",&CMap::removeObjectByName )
    .def ( "removeObject",&CMap::removeObject )
    .def ( "replaceTile",&CMap::replaceTile )
    .def ( "getPlayer",&CMap::getPlayer,return_internal_reference<>() )
    .def ( "getLocationByName",&CMap::getLocationByName )
    .def ( "removeAll",&CMap::removeAll<object> )
    .def ( "getObjectHandler",&CMap::getObjectHandler,return_internal_reference<>() )
    .def ( "getEventHandler",&CMap::getEventHandler,return_internal_reference<>() )
    .def ( "addObject",&CMap::addObject )
    .def ( "getGame",&CMap::getGame, return_internal_reference<>() );
    class_<CObjectHandler,boost::noncopyable> ( "CObjectHandler",no_init )
    .def ( "createObject",&CObjectHandler::createObject<CGameObject*>,return_internal_reference<>() );
    void ( CMapObject::*moveTo ) ( int,int,int ) =&CMapObject::moveTo ;
    class_<CMapObject,bases<CGameObject>,boost::noncopyable> ( "CMapObject",no_init )
    .def ( "getMap",&CMapObject::getMap,return_internal_reference<>() )
    .def ( "moveTo",moveTo )
    .def ( "getCoords",&CMapObject::getCoords )
    .def ( "setCoords",&CMapObject::setCoords );
    class_<CEvent,bases<CMapObject>,boost::noncopyable> ( "CEventBase" );
    class_<CInteraction,bases<CGameObject>,boost::noncopyable> ( "CInteraction" )
    .def ( "onAction",&CInteraction::onAction , return_internal_reference<>() );
    class_<CEffect,bases<CGameObject>,boost::noncopyable> ( "CEffectBase"  )
    .def ( "getBonus",&CEffect::getBonus , return_internal_reference<>() )
    .def ( "setBonus",&CEffect::setBonus )
    .def ( "getCaster",&CEffect::getCaster  , return_internal_reference<>() )
    .def ( "getVictim",&CEffect::getVictim , return_internal_reference<>() )
    .def ( "getTimeLeft",&CEffect::getTimeLeft );
    class_<CEffectWrapper,bases<CEffect>,boost::noncopyable,boost::shared_ptr<CEffectWrapper>> ( "CEffect" )
            .def ( "onEffect",&CEffectWrapper::onEffect );
    class_<CItem,bases<CMapObject>,boost::noncopyable> ( "CItem" );
    class_<CWeapon,bases<CItem>,boost::noncopyable> ( "CWeapon" )
    .def ( "getInteraction",&CWeapon::getInteraction, return_internal_reference<>() );
    class_<CBuilding,bases<CMapObject>,boost::noncopyable> ( "CBuildingBase" );
    void ( CCreature::*hurtInt ) ( int ) = &CCreature::hurt;
    void ( CCreature::*hurtDmg ) ( Damage ) = &CCreature::hurt;
    class_<CCreature,bases<CMapObject>,boost::noncopyable> ( "CCreature",no_init )
    .def ( "getDmg",&CCreature::getDmg )
    .def ( "hurt",hurtInt )
    .def ( "hurt",hurtDmg )
    .def ( "getWeapon",&CCreature::getWeapon, return_internal_reference<>() )
    .def ( "getHpRatio",&CCreature::getHpRatio )
    .def ( "isAlive",&CCreature::isAlive )
    .def ( "getMana",&CCreature::getMana )
    .def ( "healProc",&CCreature::healProc )
    .def ( "heal",&CCreature::heal )
    .def ( "getHpMax",&CCreature::getHpMax )
    .def ( "getLevel",&CCreature::getLevel )
    .def ( "getStats",&CCreature::getStats )
    .def ( "addManaProc",&CCreature::addManaProc )
    .def ( "isPlayer",&CCreature::isPlayer )
    .def ( "trade",&CCreature::trade );
    class_<CPlayer,bases<CCreature>,boost::noncopyable> ( "CPlayer" )
    .def ( "addQuest",&CPlayer::addQuest );
    class_<CMonster,bases<CCreature>,boost::noncopyable> ( "CMonster" );
    class_<CWrapper<CBuilding>,bases<CBuilding>,boost::noncopyable,boost::shared_ptr<CWrapper<CBuilding>> > ( "CBuilding" )
            .def ( "onCreate",&CWrapper<CBuilding>::onCreate )
            .def ( "onTurn",&CWrapper<CBuilding>::onTurn )
            .def ( "onDestroy",&CWrapper<CBuilding>::onDestroy )
            .def ( "onLeave",&CWrapper<CBuilding>::onLeave )
            .def ( "onEnter",&CWrapper<CBuilding>::onEnter );
    class_<CWrapper<CEvent>,bases<CEvent>,boost::noncopyable,boost::shared_ptr<CWrapper<CEvent>> > ( "CEvent" )
            .def ( "onCreate",&CWrapper<CEvent>::onCreate )
            .def ( "onTurn",&CWrapper<CEvent>::onTurn )
            .def ( "onLeave",&CWrapper<CEvent>::onLeave )
            .def ( "onDestroy",&CWrapper<CEvent>::onDestroy )
            .def ( "onEnter",&CWrapper<CEvent>::onEnter );
    class_<CInteractionWrapper,bases<CInteraction>,boost::noncopyable,boost::shared_ptr<CInteractionWrapper> > ( "CInteraction" )
    .def ( "performAction",&CInteractionWrapper::performAction )
    .def ( "configureEffect",&CInteractionWrapper::configureEffect );
    class_<Damage,bases<CGameObject>> ( "Damage" );
    class_<Stats,bases<CGameObject>> ( "Stats" );
    class_<AGamePanel,boost::noncopyable> ( "AGamePanel",no_init )
    .def ( "showPanel",&AGamePanel::showPanel );
    class_<CTextPanel,bases<AGamePanel>,boost::noncopyable> ( "CTextPanel" );
    class_<CFightPanel,bases<AGamePanel>,boost::noncopyable> ( "CFightPanel" );
    class_<CCharPanel,bases<AGamePanel>,boost::noncopyable> ( "CCharPanel" );
    class_<CGuiHandler,boost::noncopyable> ( "CGuiHandler",no_init )
    .def ( "showMessage",&CGuiHandler::showMessage )
    .def ( "showPanel",&CGuiHandler::showPanel )
    .def ( "hidePanel",&CGuiHandler::hidePanel )
    .def ( "flipPanel",&CGuiHandler::flipPanel ) ;
    class_<CTile,bases<CGameObject>,boost::noncopyable> ( "CTileBase" );
    class_<CTileWrapper,bases<CTile>,boost::noncopyable,boost::shared_ptr<CTileWrapper> > ( "CTile" ).
    def ( "onStep",&CTileWrapper::onStep );
    class_<CPotion,bases<CItem>,boost::noncopyable> ( "CItemBase" );
    class_<CPotionWrapper,bases<CPotion>,boost::noncopyable,boost::shared_ptr<CPotionWrapper> > ( "CPotion" ).
    def ( "onUse",&CPotionWrapper::onUse );
    class_<CGameEvent,boost::noncopyable> ( "CGameEvent",no_init );
    class_<CGameEventCaused,bases<CGameEvent>,boost::noncopyable> ( "CGameEventCaused",no_init )
    .def ( "getCause",&CGameEventCaused::getCause,return_internal_reference<>() );
    class_<CTrigger,bases<CGameObject>,boost::noncopyable> ( "CTriggerBase",no_init );
    class_<CTriggerWrapper,bases<CTrigger>,boost::noncopyable,boost::shared_ptr<CTriggerWrapper>> ( "CTrigger" )
            .def ( "trigger",&CTriggerWrapper::trigger );
    class_<CQuest,bases<CGameObject>,boost::noncopyable> ( "CQuestBase",no_init );
    class_<CQuestWrapper,bases<CQuest>,boost::noncopyable,boost::shared_ptr<CQuestWrapper>> ( "CQuest" )
            .def ( "isCompleted",&CQuestWrapper::isCompleted )
            .def ( "onComplete",&CQuestWrapper::onComplete );
    class_<CEventHandler,boost::noncopyable> ( "CEventHandler",no_init ).def ( "registerTrigger",&CEventHandler::registerTrigger );
    class_<CGame,boost::noncopyable> ( "CGame",no_init )
    .def ( "getMap",&CGame::getMap,return_internal_reference<>() )
    .def ( "changeMap",&CGame::changeMap )
    .def ( "getGuiHandler",&CGame::getGuiHandler,return_internal_reference<>() );
}
