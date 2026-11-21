"""Calamares mounted-target package job."""

from pathlib import Path
import sys

import libcalamares

sys.path.insert(0, "/usr/lib/calamares/modules/aphroditeprofiles")
from executor import apply, TARGET_LOG, TransactionError
from selection import validate


def pretty_name():
    return "Install selected packages"


def run():
    storage = libcalamares.globalstorage
    messages = []

    def report(message):
        messages.append(message)
        libcalamares.utils.warning(message)
        storage.insert("seanProfileReport", "\n".join(messages))

    try:
        plan = validate(storage.value("packagechooser_aphroditepackages"))
    except (ValueError, TypeError) as error:
        return "Invalid package selection", str(error)
    try:
        root = storage.value("rootMountPoint")
        if not isinstance(root, str) or not root:
            raise ValueError("Calamares did not supply a mounted target")
        apply(root, plan, report, live_log=Path("/") / TARGET_LOG)
    except (ValueError, OSError, TransactionError) as error:
        return "Target package setup failed", str(error)
    return None
