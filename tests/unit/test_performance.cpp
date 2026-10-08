/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include "core/CRuntimeBridge.h"
#include "core/CPlaytestTrace.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <memory>
#include <set>
#include <string>
#include <vector>

void run_pathfinder_performance_tests();
void run_engine_hotspot_performance_tests();
void run_serialization_performance_tests();
void run_render_context_performance_tests();

namespace {
class JournalCaptureCountQuest : public CQuest {
  public:
    void captureJournal(bool completed) override {
        ++captureCalls;
        completedCaptureCalls += completed ? 1 : 0;
    }

    bool isCompleted() override {
        ++completionChecks;
        return true;
    }

    void onComplete() override { ++completionCallbacks; }

    std::string getObjective() override {
        ++textReads;
        return "objective";
    }

    std::string getReward() override {
        ++textReads;
        return "reward";
    }

    std::string getHint() override {
        ++textReads;
        return "hint";
    }

    int captureCalls = 0;
    int completedCaptureCalls = 0;
    int completionChecks = 0;
    int completionCallbacks = 0;
    int textReads = 0;
};

void run_quest_journal_performance_guard() {
    constexpr int ACTIVE_QUESTS = 96;
    constexpr int COMPLETED_QUESTS = 32;
    constexpr int CAPTURE_PASSES = 3;
    auto player = std::make_shared<CPlayer>();
    std::set<std::shared_ptr<CQuest>> active;
    std::set<std::shared_ptr<CQuest>> completed;
    std::vector<std::shared_ptr<JournalCaptureCountQuest>> probes;
    for (int index = 0; index < ACTIVE_QUESTS + COMPLETED_QUESTS; ++index) {
        auto quest = std::make_shared<JournalCaptureCountQuest>();
        probes.push_back(quest);
        (index < ACTIVE_QUESTS ? active : completed).insert(quest);
    }
    player->setQuests(active);
    player->setCompletedQuests(completed);
    for (int pass = 0; pass < CAPTURE_PASSES; ++pass) {
        player->captureQuestJournal();
    }
    int totalCalls = 0;
    for (int index = 0; index < static_cast<int>(probes.size()); ++index) {
        const auto &quest = probes[index];
        totalCalls += quest->captureCalls;
        expect_true(quest->captureCalls == CAPTURE_PASSES, "journal capture must visit each quest once per pass");
        expect_true(quest->completedCaptureCalls == (index < ACTIVE_QUESTS ? 0 : CAPTURE_PASSES),
                    "journal capture must preserve active/completed set membership");
        expect_true(quest->completionChecks == 0 && quest->completionCallbacks == 0,
                    "journal capture must not run completion checks or grant rewards");
        expect_true(quest->textReads == 0, "native journal capture must delegate text collection to its callback");
    }
    expect_true(player->getQuests() == active && player->getCompletedQuests() == completed,
                "journal capture must not change quest collections");
    expect_true(totalCalls == (ACTIVE_QUESTS + COMPLETED_QUESTS) * CAPTURE_PASSES,
                "journal capture callback count must stay linear in the quest count");
    std::cout << "quest journal capture guard: active=" << ACTIVE_QUESTS << " completed=" << COMPLETED_QUESTS
              << " passes=" << CAPTURE_PASSES << " callbacks=" << totalCalls
              << " budget=" << (ACTIVE_QUESTS + COMPLETED_QUESTS) * CAPTURE_PASSES << "\n";
}

void run_recent_trace_performance_guard() {
    constexpr int EVENTS = 10000;
    constexpr std::size_t RETAINED_RECORDS = 32;
    CPlaytestTrace::configure(true, "", RETAINED_RECORDS, true);
    for (int index = 1; index <= EVENTS; ++index) {
        CPlaytestTrace::record("bounded_diagnostic_event", {{"index", index}});
    }
    const auto records = CPlaytestTrace::records();
    expect_true(records.size() == RETAINED_RECORDS, "recent trace storage must stay within its fixed record budget");
    for (std::size_t index = 0; index < records.size(); ++index) {
        const auto record = json::parse(records[index]);
        const auto expected = EVENTS - RETAINED_RECORDS + index + 1;
        expect_true(record["seq"].get<unsigned long long>() == expected &&
                        record["index"].get<unsigned long long>() == expected,
                    "bounded trace storage must preserve the latest sequence without dropping new events");
    }
    CPlaytestTrace::configure(false, "", RETAINED_RECORDS, true);
    for (int index = 0; index < EVENTS; ++index) {
        CPlaytestTrace::record("disabled_diagnostic_event");
    }
    expect_true(CPlaytestTrace::records().empty(), "disabled tracing must not retain diagnostic records");
    std::cout << "recent trace guard: events=" << EVENTS << " retained=" << records.size()
              << " budget=" << RETAINED_RECORDS << " first-seq=" << EVENTS - RETAINED_RECORDS + 1
              << " last-seq=" << EVENTS << " disabled-events=" << EVENTS << "\n";
}
} // namespace

int main() {
    pybind11::scoped_interpreter guard{};
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");

    run_pathfinder_performance_tests();
    run_engine_hotspot_performance_tests();
    run_serialization_performance_tests();
    run_render_context_performance_tests();
    run_quest_journal_performance_guard();
    run_recent_trace_performance_guard();

    return finish_tests();
}
