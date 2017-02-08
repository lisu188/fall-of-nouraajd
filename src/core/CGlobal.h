#pragma once

#include <Python.h>

#include <boost/python.hpp>
#include <boost/python/suite/indexing/vector_indexing_suite.hpp>
#include <boost/locale.hpp>
#include <boost/filesystem.hpp>
#include <boost/range/algorithm.hpp>

#include <SDL.h>
#include <SDL_image.h>

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
#include <signal.h>
#include <sstream>
#include <stdio.h>
#include <thread>
#include <time.h>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <json/json.h>
#include <vstd.h>

//TODO: rethink this
#define TILE_SIZE 50
#define WIDTH 1920
#define HEIGHT 1080
#define X_SIZE WIDTH/TILE_SIZE
#define Y_SIZE HEIGHT/TILE_SIZE
#define FPS 100

using namespace Json;