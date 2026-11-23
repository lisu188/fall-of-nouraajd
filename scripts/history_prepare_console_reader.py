"""Replay the #204 console reader with an event-loop-owned stdin notifier."""

import hashlib
from pathlib import Path

COMMIT = "c577f6225739c5e3e1cf90081a92e997eaed65a4"
TARGET = "src/main.cpp"
INPUT_SHA256 = "afcbca06c54f7e48aeb125cca228287b4b49ced0ead968b3a7c74def3311f589"
OUTPUT_SHA256 = "f9d901efbaee53e5c818fc9f2144ed5ec5fcb39b5e34406663178492d7162377"
PURPOSE = "Read console commands on stdin readiness and release the reader at shutdown"
ORIGINAL = b"""    QThreadPool::globalInstance()->start(new GameTask([]()->void{
        QTextStream streamIn(stdin);
        QString script;
        while((!GameScene::getView())||GameScene::getView()->isVisible()){
            streamIn>>script;
            ScriptManager::getInstance().executeScript(script.toStdString());
        }
    }));"""
REPLACEMENT = b"""    QSocketNotifier console(STDIN_FILENO, QSocketNotifier::Read, &a);
    QByteArray script;
    auto execute = [&script]() {
        if (!script.isEmpty()) {
            ScriptManager::getInstance().executeScript(script.toStdString());
            script.clear();
        }
    };
    QObject::connect(&console, &QSocketNotifier::activated, &a, [&](int fd) {
        char data[4096];
        const ssize_t size = read(fd, data, sizeof(data));
        if (size <= 0) {
            if (size == 0) {
                console.setEnabled(false);
                execute();
            } else if (errno != EINTR && errno != EAGAIN) {
                console.setEnabled(false);
            }
            return;
        }
        for (ssize_t index = 0; index < size; ++index) {
            const unsigned char value = data[index];
            if (std::isspace(value)) {
                execute();
            } else {
                script.append(static_cast<char>(value));
            }
        }
    });"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(source):
    if digest(source) != INPUT_SHA256 or source.count(ORIGINAL) != 1:
        raise ValueError("Console reader source differs from the reviewed #204 original")
    headers = b"#include <QSocketNotifier>\n#include <cerrno>\n#include <cctype>\n#include <unistd.h>\n"
    result = source.replace(b"#include <QThreadPool>\n", b"#include <QThreadPool>\n" + headers).replace(
        ORIGINAL, REPLACEMENT
    )
    if digest(result) != OUTPUT_SHA256:
        raise ValueError("Console reader output differs from the reviewed #204 build copy")
    return result


def validate(preparation):
    expected = {
        "sourceCommit": COMMIT,
        "inputSha256": INPUT_SHA256,
        "outputSha256": OUTPUT_SHA256,
        "replaySha256": digest(Path(__file__).read_bytes()),
    }
    rows = [row for row in preparation.get("outputs", []) if row.get("path") == TARGET]
    if preparation.get("identity", {}).get("consoleReader") != expected or rows != [
        {
            "path": TARGET,
            "before": {"kind": "file", "sha256": INPUT_SHA256},
            "after": {"kind": "file", "sha256": OUTPUT_SHA256},
            "purpose": PURPOSE,
        }
    ]:
        raise ValueError("Console reader preparation lacks the pinned source fingerprints")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    path = root / TARGET
    if path.resolve() != root / TARGET or path.is_symlink():
        raise ValueError("Console reader source traverses a symbolic link")
    path.write_bytes(prepare(path.read_bytes()))
