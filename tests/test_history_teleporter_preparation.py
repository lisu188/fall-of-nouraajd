# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts import history_prepare_teleporter as helper
from scripts import history_source_prep as source_prep

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name("fixtures") / "history_teleporter"
JSONCPP = REPO / "recovery/upstream/libraries/jsoncpp-0.5.0"


class TeleporterPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source"
        (self.root / "buildings").mkdir(parents=True)
        (self.root / "json").mkdir()
        self.state(164)

    def state(self, position):
        for suffix in ["cpp", "h"]:
            (self.root / "buildings" / ("teleporter." + suffix)).write_bytes(
                (FIXTURES / f"{position}-teleporter.{suffix}").read_bytes()
            )
        (self.root / "json/json_value.cpp").write_bytes((JSONCPP / "json__json_value.cpp").read_bytes())

    def evidence(self):
        plan = helper.teleporterPlan(self.root)
        evidence = Path(self.temporary.name) / "evidence"
        evidence.mkdir(exist_ok=True)
        outputs = [{"path": helper.TARGET, "before": None, "after": {"kind": "file", "sha256": plan["sha256"]}}]
        report = {
            "status": "success",
            "qmakeArguments": helper.ARGUMENTS,
            "outputs": outputs,
            "identity": {
                "teleporterSerialization": {key: value for key, value in plan.items() if key != "data"},
                "outputs": outputs,
            },
        }
        (evidence / "source-preparation.json").write_text(json.dumps(report))
        (evidence / helper.ATTACHMENT).write_bytes(plan["data"])
        return evidence

    def testAllKnownOriginalStatesProducePinnedDerivedSource(self):
        for position in [164, 175, 176, 178]:
            with self.subTest(position=position):
                self.state(position)
                original = (self.root / helper.SOURCE).read_bytes()
                plan = helper.teleporterPlan(self.root)
                self.assertEqual(
                    hashlib.sha256(plan["data"]).hexdigest(), helper.OUTPUTS[hashlib.sha256(original).hexdigest()]
                )
                self.assertIn(b"bool enabled", (self.root / "buildings/teleporter.h").read_bytes())
                old = original
                new = plan["data"]
                for name in ["saveToJson", "loadFromJson"]:
                    a, b = helper.methodBody(old, name)
                    old = old[:a] + b"BODY" + old[b:]
                    a, b = helper.methodBody(new, name)
                    new = new[:a] + b"BODY" + new[b:]
                self.assertEqual(old, new)

    def testChangedCppHeaderOrJsonImplementationNotSelected(self):
        for name in [helper.SOURCE, "buildings/teleporter.h", "json/json_value.cpp"]:
            self.state(164)
            p = self.root / name
            p.write_bytes(p.read_bytes() + b"\n")
            self.assertIsNone(helper.teleporterPlan(self.root))

    def testSourcePreparationRecordsOnlyDerivedUnitAndPreservesOriginals(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with tempfile.TemporaryDirectory() as directory:
            report = source_prep.prepareSources(
                self.root,
                Path(directory),
                {"pythonAbi": "none"},
                {},
                lambda *args, **kwargs: self.fail("Teleporter generation needs no external generator"),
            )
        self.assertEqual(report["status"], "success")
        self.assertEqual([step["name"] for step in report["steps"]], ["teleporterSerialization"])
        self.assertEqual(report["qmakeArguments"], helper.ARGUMENTS)
        self.assertEqual(source_prep.preparationArguments(self.root), helper.ARGUMENTS)
        self.assertEqual([entry["path"] for entry in report["outputs"]], [helper.TARGET])
        self.assertIsNone(report["outputs"][0]["before"])
        self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))

    def testPortableReplayIsIdempotentAndOriginalsRemainUnchanged(self):
        evidence = self.evidence()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertTrue(helper.prepareTeleporter(self.root, evidence))
        self.assertFalse(helper.prepareTeleporter(self.root, evidence))
        self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))

    def testTamperedDerivedAttachmentAndSelfConsistentMetadataRejected(self):
        evidence = self.evidence()
        p = evidence / helper.ATTACHMENT
        p.write_bytes(b"forged")
        with self.assertRaisesRegex(ValueError, "attachment differs"):
            helper.prepareTeleporter(self.root, evidence)
        metadata = evidence / "source-preparation.json"
        report = json.loads(metadata.read_text())
        report["identity"]["teleporterSerialization"]["sha256"] = hashlib.sha256(b"forged").hexdigest()
        report["outputs"][0]["after"]["sha256"] = hashlib.sha256(b"forged").hexdigest()
        metadata.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            helper.prepareTeleporter(self.root, evidence)

    def testConflictSymlinkAndUnknownSourceRejected(self):
        evidence = self.evidence()
        target = self.root / helper.TARGET
        target.write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "different bytes"):
            helper.prepareTeleporter(self.root, evidence)
        target.unlink()
        target.symlink_to(self.root / "outside")
        with self.assertRaisesRegex(ValueError, "symlink"):
            helper.prepareTeleporter(self.root, evidence)
        target.unlink()
        header = self.root / "buildings/teleporter.h"
        header.unlink()
        header.symlink_to(self.root / "outside")
        with self.assertRaisesRegex(ValueError, "symlink"):
            helper.teleporterPlan(self.root)

    def testChangedFlagsAndOutputFingerprintsRejected(self):
        evidence = self.evidence()
        p = evidence / "source-preparation.json"
        text = p.read_text()
        report = json.loads(text)
        report["qmakeArguments"] = helper.ARGUMENTS[1:]
        p.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            helper.prepareTeleporter(self.root, evidence)
        report = json.loads(text)
        report["identity"]["outputs"] = []
        p.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "fingerprints differ"):
            helper.prepareTeleporter(self.root, evidence)

    @unittest.skipUnless(shutil.which("g++"), "Native compiler unavailable")
    def testNativeOriginalAbortsAndDerivedRoundtripsCoordinatesAndEnabled(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            includes = work / "include"
            headers = includes / "json"
            headers.mkdir(parents=True)
            for p in JSONCPP.glob("json__*"):
                shutil.copyfile(p, headers / p.name[len("json__") :])
            for name in ["config.h", "forwards.h"]:
                shutil.copyfile(FIXTURES / ("json-" + name), headers / name)
            objects = []
            for name in ["json_value", "json_writer"]:
                target = work / (name + ".o")
                command = [
                    "g++",
                    "-std=c++11",
                    "-O0",
                    "-I" + str(includes),
                    "-c",
                    str(headers / (name + ".cpp")),
                    "-o",
                    str(target),
                ]
                r = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr[-3000:])
                objects.append(str(target))
            declaration = """#include <json/value.h>
class Teleporter {
public:
 bool enabled=true; int x=0,y=0,z=0;
 int getPosX(){return x;} int getPosY(){return y;} int getPosZ(){return z;}
 void moveTo(int a,int b,int c,bool){x=a;y=b;z=c;}
 Json::Value saveToJson(); void loadFromJson(Json::Value config);
};
"""
            main = """int main(){
 for(int enabled=0;enabled!=2;++enabled){
  Teleporter before;before.moveTo(-4,9,2,true);before.enabled=enabled;
  Json::Value data=before.saveToJson();
  if(!data.isObject()||data["x"].asInt()!=-4||data["y"].asInt()!=9||data["z"].asInt()!=2||data["enabled"].asBool()!=bool(enabled))return 1;
  Teleporter after;after.enabled=!enabled;after.loadFromJson(data);
  if(after.x!=-4||after.y!=9||after.z!=2||after.enabled!=bool(enabled))return 2;
  Json::Value old;old[0u]=-2;old[1u]=5;old[2u]=7;
  after.loadFromJson(old);
  if(after.x!=-2||after.y!=5||after.z!=7||after.enabled!=bool(enabled))return 3;
 }
 return 0;
}
"""
            for position in [164, 175, 176, 178]:
                self.state(position)
                original = (self.root / helper.SOURCE).read_bytes()
                derived = helper.teleporterPlan(self.root)["data"]
                for kind, data in [("original", original), ("derived", derived)]:
                    with self.subTest(position=position, kind=kind):
                        methods = []
                        for name in ["saveToJson", "loadFromJson"]:
                            start, end = helper.methodBody(data, name)
                            signature = data.rfind(b"\n", 0, data.rfind(b"Teleporter::", 0, start)) + 1
                            methods.append(data[signature : end + 1].decode())
                        source = work / "probe.cpp"
                        source.write_text(declaration + "\n".join(methods) + main)
                        binary = work / "probe"
                        r = subprocess.run(
                            [
                                "g++",
                                "-std=c++11",
                                "-O0",
                                "-I" + str(includes),
                                str(source),
                                *objects,
                                "-o",
                                str(binary),
                            ],
                            capture_output=True,
                            text=True,
                        )
                        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
                        r = subprocess.run([str(binary)], capture_output=True, text=True, cwd=work)
                        if kind == "original":
                            self.assertNotEqual(r.returncode, 0)
                            self.assertIn("Assertion", r.stderr)
                        else:
                            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
