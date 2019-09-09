//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#include "core/CGame.h"
#include "core/CLoader.h"
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
            .def("loadGui", &CGameLoader::loadGui)
            .def("loadSavedGame", &CGameLoader::loadSavedGame);
    class_<CMapLoader, boost::noncopyable, std::shared_ptr<CMapLoader>>("CMapLoader", no_init)
            .def("loadNewMapWithPlayer", &CMapLoader::loadNewMapWithPlayer)
            .def("loadNewMap", &CMapLoader::loadNewMap);

    class_<CPlugin, bases<CGameObject>, boost::noncopyable, std::shared_ptr<CPlugin>>("CPluginBase", no_init);
    class_<CWrapper<CPlugin>, bases<CPlugin>, boost::noncopyable, std::shared_ptr<CWrapper<CPlugin>>>("CPlugin").
            def("load", &CWrapper<CPlugin>::load);

    class_<vstd::event_loop<>, boost::noncopyable, std::shared_ptr<vstd::event_loop<>>>("event_loop", no_init)
            .def("instance", &vstd::event_loop<>::instance)
            .def("run", &vstd::event_loop<>::run)
            .def("invoke", &vstd::event_loop<>::invoke);

    class_<std::vector<std::string>>("std::vector<std::string>")
            .def(vector_indexing_suite<std::vector<std::string>>());
}