"""Canonical catalog and versioned package selection."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = json.loads((HERE / "catalog.json").read_text())
APPS = {app["id"]: app for app in CATALOG["apps"]}
DEFAULT = "firefox"
MODES = ("off", "desktop", "gaming")
LEGACY = ("off", "games", "desktop", "gaming")


def available(app, desktop="plasma"):
    return bool(app["methods"]) and app["desktop"] in ("any", desktop)


def preset(name, metadata=None):
    selected = {DEFAULT: "apt"}
    for app in APPS.values():
        if not available(app) or app["category"] == "browser":
            continue
        if name == "Recommended" and app["recommended"]:
            selected[app["id"]] = "apt"
        elif (name == "Full" and app["full"] and not app["large"]
              and app["license"] == "open-source" and metadata
              and metadata.get(app["id"], {}).get("apt", {}).get("full")):
            selected[app["id"]] = "apt"
    return selected


def validate(value):
    """Return a fresh plan. Only known application IDs and methods survive validation."""
    if not value:
        value = "off"
    if isinstance(value, str):
        mode = value.removesuffix("-resolve")
        if mode in LEGACY:
            ids = preset("Minimal")
            if mode != "off":
                ids.update(steam="apt", gamemode="apt", mangohud="apt")
            if mode in ("desktop", "gaming"):
                ids["gamescope"] = "apt"
            return dict(version=1, apps=ids, browser=DEFAULT,
                        session=mode if mode in MODES else "off",
                        legacy_gaming=mode != "off", legacy_resolve=value.endswith("-resolve"))
        if len(value) > 8192:
            raise ValueError("Package selection is too long")
        value = json.loads(value)
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("Unknown package selection version")
    ids = value.get("apps")
    if not isinstance(ids, dict) or len(ids) > len(APPS):
        raise ValueError("Expected an application-to-method map")
    for key, method in ids.items():
        if (key not in APPS or not available(APPS[key]) or not isinstance(method, str)
                or method not in APPS[key]["methods"]):
            raise ValueError(f"Unavailable application or method for {key!r}")
    browser = value.get("browser")
    if browser is None and any(APPS[key]["category"] == "browser" for key in ids):
        raise ValueError("Choose a primary browser for the selected browsers")
    if browser is not None and (not isinstance(browser, str) or browser not in ids or APPS[browser]["category"] != "browser"):
        raise ValueError("Select an installed browser as the default")
    mode = value.get("session")
    if mode not in MODES:
        raise ValueError("Unknown gaming session mode")
    if mode != "off" and (ids.get("steam"), ids.get("gamescope")) != ("apt", "apt"):
        raise ValueError("The dedicated session requires native Steam and Gamescope")
    pins = value.get("pins", {"enabled": True, "core": True, "apps": []})
    if (not isinstance(pins, dict) or type(pins.get("enabled", True)) is not bool
            or type(pins.get("core", True)) is not bool or not isinstance(pins.get("apps", []), list)
            or any(not isinstance(key, str) or key not in ids for key in pins.get("apps", []))):
        raise ValueError("Pin selections must refer to selected applications")
    return dict(version=1, apps=dict(ids), browser=browser, session=mode,
                pins={"enabled": pins.get("enabled", True), "core": pins.get("core", True),
                      "apps": list(dict.fromkeys(pins.get("apps", [])))},
                legacy_gaming=False, legacy_resolve=False)
