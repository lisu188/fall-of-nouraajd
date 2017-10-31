#include "core/CLoader.h"
#include "core/CEventLoop.h"
#include "core/CWrapper.h"

using namespace boost::python;

void initModule3() {
    class_<CEventHandler, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEventHandler>>("CEventHandler",
                                                                                                  no_init)
            .def("registerTrigger", &CEventHandler::registerTrigger);

    class_<CFightHandler, boost::noncopyable, std::shared_ptr<CFightHandler>>("CFightHandler", no_init)
            .def("fight", &CFightHandler::fight);

    class_<CMarket, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMarket> >("CMarket");

    class_<CGameLoader, boost::noncopyable, std::shared_ptr<CGameLoader>>("CGameLoader", no_init)
            .def("loadGame", &CGameLoader::loadGame)
            .def("startGameWithPlayer", &CGameLoader::startGameWithPlayer)
            .def("startGame", &CGameLoader::startGame)
            .def("loadGui", &CGameLoader::loadGui);
    class_<CMapLoader, boost::noncopyable, std::shared_ptr<CMapLoader>>("CMapLoader", no_init)
            .def("loadNewMapWithPlayer", &CMapLoader::loadNewMapWithPlayer)
            .def("loadNewMap", &CMapLoader::loadNewMap);

    class_<CPlugin, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CPlugin>>("CPluginBase", no_init);
    class_<CWrapper<CPlugin>, bases<CPlugin>, boost::noncopyable, std::shared_ptr<CWrapper<CPlugin>>>("CPlugin").
            def("load", &CWrapper<CPlugin>::load);

    class_<CMapPlugin, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CMapPlugin>>("CMapPluginBase", no_init);
    class_<CWrapper<CMapPlugin>, bases<CMapPlugin>, boost::noncopyable, std::shared_ptr<CWrapper<CMapPlugin>>>(
            "CMapPlugin").
            def("load", &CWrapper<CMapPlugin>::load);

    class_<CEventLoop, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CEventLoop>>("CEventLoop", no_init)
            .def("instance", &CEventLoop::instance)
            .def("run", &CEventLoop::run)
            .def("invoke", &CEventLoop::invoke);

    class_<std::vector<std::string>>("std::vector<std::string>")
            .def(vector_indexing_suite<std::vector<std::string>>());
}