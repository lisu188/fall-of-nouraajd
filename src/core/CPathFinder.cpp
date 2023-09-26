/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "core/CPathFinder.h"

typedef std::function<bool(const Coords &, const Coords &)> Compare;
typedef std::priority_queue<Coords, std::vector<Coords>, Compare> Queue;
typedef std::shared_ptr<std::unordered_map<Coords, int>> Values;

static Coords getNextStep(const Coords &start, const Coords &goal, const Values &values,
                          const std::function<std::pair<bool, Coords>(const Coords &)> waypoint) {
    Coords target = start;
    std::list<Coords> list = near_coords(start);
    auto it = waypoint(start);
    if (it.first) {
        list.push_back(it.second);
    }
    for (Coords coords: list) {
        if (vstd::ctn((*values), coords) &&
            ((*values)[coords] < (*values)[target] ||
             ((*values)[coords] == (*values)[target] &&
              coords.getDist(goal) < target.getDist(goal)))) {
            target = coords;
        }
    }
    return target;
}

static Values fillValues(const std::function<bool(const Coords &)> &canStep,
                         const Coords &goal, const Coords &start,
                         const std::function<std::pair<bool, Coords>(const Coords &)> waypoint) {
    Queue nodes([start](const Coords &a, const Coords &b) {
        double dista = (a.x - start.x) * (a.x - start.x) +
                       (a.y - start.y) * (a.y - start.y);
        double distb = (b.x - start.x) * (b.x - start.x) +
                       (b.y - start.y) * (b.y - start.y);
        return dista > distb;
    });
    std::unordered_set<Coords> marked;
    Values values = std::make_shared<std::unordered_map<Coords, int>>();

    if (canStep(goal)) {
        nodes.push(goal);
        (*values)[goal] = 0;
    }

    while (!nodes.empty() && !vstd::ctn(marked, start)) {
        Coords currentCoords = vstd::pop_p(nodes);
        if (marked.insert(currentCoords).second) {
            int curValue = (*values)[currentCoords];
            auto waypoint_direction = waypoint(currentCoords);
            auto list = near_coords(currentCoords);
            if (waypoint_direction.first) {
                list.push_back(waypoint_direction.second);
            }
            for (Coords tmpCoords: list) {
                if (tmpCoords == start || canStep(tmpCoords)) {
                    auto it = values->find(tmpCoords);
                    if (it == values->end() || it->second > curValue + 1) {
                        (*values)[tmpCoords] = curValue + 1;
                    }
                    nodes.push(tmpCoords);
                }
            }
        }
    }
    return values;
}

static Values fillAllValues(const std::function<bool(const Coords &)> &canStep, const Coords &goal,
                            const std::function<std::pair<bool, Coords>(const Coords &)> waypoint) {
    std::unordered_set<Coords> marked;
    Values values = std::make_shared<std::unordered_map<Coords, int>>();
    Queue nodes([values](const Coords &a, const Coords &b) {
        int dista;
        auto it = values->find(a);
        if (it == values->end()) {
            dista = std::numeric_limits<int>::max();
        } else {
            dista = it->second;
        }
        int distb;
        it = values->find(b);
        if (it == values->end()) {
            distb = std::numeric_limits<int>::max();
        } else {
            distb = it->second;
        }
        return dista > distb;
    });
    nodes.push(goal);
    (*values)[goal] = 0;

    while (!nodes.empty()) {
        Coords currentCoords = vstd::pop_p(nodes);
        if (marked.insert(currentCoords).second) {
            int curValue = (*values)[currentCoords];
            auto list = near_coords(currentCoords);
            auto waypoint_direction = waypoint(currentCoords);
            if (waypoint_direction.first) {
                list.push_back(waypoint_direction.second);
            }
            for (Coords tmpCoords: list) {
                if (canStep(tmpCoords)) {
                    auto it = values->find(tmpCoords);
                    if (it == values->end() || it->second > curValue + 1) {
                        (*values)[tmpCoords] = curValue + 1;
                    }
                    nodes.push(tmpCoords);
                }
            }
        }
    }
    return values;
}

std::shared_ptr<vstd::future<Coords, void>> CPathFinder::findNextStep(Coords start, Coords goal,
                                                                      const std::function<bool(
                                                                              const Coords &)> &canStep,
                                                                      const std::function<std::pair<bool, Coords>(
                                                                              const Coords &)> waypoint) {
    return vstd::async([=]() {
        return getNextStep(start, goal, fillValues(
                canStep, goal, start, waypoint), waypoint);
    });
}

std::vector<Coords>
CPathFinder::findPath(Coords start, Coords goal, const std::function<bool(const Coords &)> &canStep,
                      const std::function<std::pair<bool, Coords>(
                              const Coords &)> waypoint) {
    std::vector<Coords> path;
    Values val = fillValues(canStep, goal, start, waypoint);
    Coords next = getNextStep(start, goal, val, waypoint);
    path.push_back(next);
    if (next != start) {
        while (next != goal) {
            next = getNextStep(next, goal, val, waypoint);
            path.push_back(next);
        }
    }
    return path;
}

void CPathFinder::saveMap(Coords start, const std::function<bool(const Coords &)> &canStep, const std::string &path,
                          const std::function<std::pair<bool, Coords>(const Coords &)> &waypoint) {
    Values values = fillAllValues(canStep, start, waypoint);
    int minx = std::numeric_limits<int>::max();
    int miny = std::numeric_limits<int>::max();
    int maxx = std::numeric_limits<int>::min();
    int maxy = std::numeric_limits<int>::min();
    int maxVal = std::numeric_limits<int>::min();
    for (std::pair<Coords, int> entry: *values) {
        Coords coords = entry.first;
        if (coords.x < minx) {
            minx = coords.x;
        }
        if (coords.y < miny) {
            miny = coords.y;
        }
        if (coords.x > maxx) {
            maxx = coords.x;
        }
        if (coords.y > maxy) {
            maxy = coords.y;
        }
        if (entry.second > maxVal) {
            maxVal = entry.second;
        }
    }
    int factor = 4;
    SDL_Surface *surface = SDL_CreateRGBSurface(0, factor * (maxx - minx), factor * (maxy - miny), 32, 0, 0, 0, 0);
    float scale = 256.0 / maxVal;
    for (std::pair<Coords, int> entry: *values) {
        int posx = entry.first.x - minx;
        int posy = entry.first.y - miny;
        int val = entry.second;
        SDL_Rect rect;
        rect.x = posx * factor;
        rect.y = posy * factor;
        rect.w = factor;
        rect.h = factor;
        SDL_FillRect(surface, &rect, SDL_MapRGB(surface->format, scale * val, scale * val, scale * val));
    }
    IMG_SavePNG(surface, path.c_str());
    SDL_FreeSurface(surface);
}

