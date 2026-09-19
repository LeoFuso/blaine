"""Read metadata only for BWS/Bitwarden candidates; never GetSecret or Unlock."""
import json
from pathlib import Path
import dbus

HERE = Path(__file__).resolve().parent
result = {"secret_values_read": False, "keyring_modified": False, "candidates": []}
try:
    bus = dbus.SessionBus()
    if not bus.name_has_owner("org.freedesktop.secrets"):
        result["status"] = "Secret Service is not running; no activation attempted"
    else:
        def props(path):
            return dbus.Interface(bus.get_object("org.freedesktop.secrets", path),
                                  "org.freedesktop.DBus.Properties")
        collections = props("/org/freedesktop/secrets").Get("org.freedesktop.Secret.Service", "Collections")
        for collection in collections:
            for item in props(collection).Get("org.freedesktop.Secret.Collection", "Items"):
                p = props(item)
                attrs = p.Get("org.freedesktop.Secret.Item", "Attributes")
                # Examine metadata locally; only structural booleans/attribute names leave this probe.
                label = str(p.Get("org.freedesktop.Secret.Item", "Label"))
                if not any(word in (label + " " + " ".join(map(str, attrs.values()))).lower()
                           for word in ["bws", "bitwarden"]):
                    continue
                result["candidates"].append({
                    "attribute_names": sorted(map(str, attrs.keys())),
                    "has_service": "service" in attrs,
                    "has_username": "username" in attrs,
                    "has_user": "user" in attrs,
                    "locked": bool(p.Get("org.freedesktop.Secret.Item", "Locked")),
                })
        result["status"] = "metadata inspected; no values or addressing identifiers retained"
except Exception as exc:
    result["status"] = "metadata unavailable"
    result["error_type"] = type(exc).__name__
(HERE / "keyring-observations.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
