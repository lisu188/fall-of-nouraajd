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
#pragma once

#include <Python.h>

#include <boost/python.hpp>
#include <boost/python/suite/indexing/vector_indexing_suite.hpp>
#include <boost/locale.hpp>
#include <boost/filesystem.hpp>
#include <boost/range/algorithm.hpp>

#include <SDL.h>
#include <SDL_image.h>
#include <SDL_ttf.h>

#include <condition_variable>
#include <deque>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <string>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <queue>
#include <random>
#include <set>
#include <csignal>
#include <sstream>
#include <cstdio>
#include <thread>
#include <limits>
#include <ctime>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <json/json.h>
#include <vstd.h>

using namespace Json;