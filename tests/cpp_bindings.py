# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Source inspection for the ordered registration groups of the production Python module."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BINDING_GROUPS = (
    ("CModuleFoundation.cpp", "bindFoundationAndSession"),
    ("CModuleWorld.cpp", "bindGraphicsAndWorld"),
    ("CModuleGameplay.cpp", "bindGameplayObjects"),
    ("CModuleServices.cpp", "bindServices"),
    ("CModuleCreatures.cpp", "bindCreatures"),
    ("CModulePanels.cpp", "bindPanelsAndUtilities"),
)
CPP_TOKENS = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|\s+|[{}]|[^{}"\'/\s]+|.',
    re.DOTALL,
)


def bindingSourcePaths(root=ROOT):
    return (root / "src/core/CModule.cpp",) + tuple(
        root / "src/core/bindings" / filename for filename, _ in BINDING_GROUPS
    )


def readBindingSources(root=ROOT):
    return "\n".join(path.read_text(encoding="utf-8") for path in bindingSourcePaths(root))


def registrationBody(source, name):
    opening = source.index("{", source.index(name + "("))
    depth = 1
    for token in CPP_TOKENS.finditer(source, opening + 1):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : token.start()]
    raise ValueError(f"Unclosed C++ registration body: {name}")


def registrationTokens(source):
    return "".join(
        value
        for token in CPP_TOKENS.finditer(source)
        if (value := token.group()) and not value.isspace() and not value.startswith(("//", "/*"))
    )
