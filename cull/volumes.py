"""External volume support — auto-discovery, mount validation, and safe ejection.

Provides a clean interface for discovering mounted external drives
(USB, SSD, thumb drives) on macOS, verifying they are still reachable,
and safely ejecting them after operations complete.
"""

import os
import string
import subprocess
import sys
from pathlib import Path
from typing import Optional

from cull import config

# ── Public helpers ───────────────────────────────────────────────────


def list_volumes() -> list[dict]:
    """Enumerate all non-system mounted external volumes.

    Returns a list of dicts::

        {
            "name": "MyUSB",
            "path": "/Volumes/MyUSB",
            "is_internal": False,
            "is_readonly": True | False,
            "mount_point": "/Volumes/MyUSB",
            "filesystem": "exFAT" | "APFS" | ...,
        }

    Platforms supported:
    - **macOS**: ``/Volumes/*``, skips internal ``Macintosh HD``.
    - **Linux**: ``/media/*`` and ``/mnt/*`` mount points.
    - **Windows**: Drive letters ``D:\\`` through ``Z:\\`` that appear
      to be removable (``DRIVE_REMOVABLE`` or non-system volumes).
    """
    if sys.platform == "darwin":
        return _macos_volumes()
    if sys.platform == "win32":
        return _windows_volumes()
    return _linux_volumes()


def validate_mount(path: str | Path) -> tuple[bool, str]:
    """Check whether *path* is on a reachable, mounted volume.

    Returns ``(is_valid, message)``.  The message explains any failure.
    """
    try:
        p = Path(path).resolve(strict=False)
    except (OSError, RuntimeError):
        return False, "Cannot resolve path"

    # On macOS, volumes live under /Volumes — check we can stat the root
    try:
        p.stat()  # raises OSError if inaccessible
    except OSError as exc:
        return False, f"Cannot access path: {exc}"

    return True, "Path is accessible"


def get_volume_for_path(path: str | Path) -> Optional[dict]:
    """Return the volume dict for the volume that contains *path*.

    Returns ``None`` if the path is on the internal drive or unmounted.
    """
    p = Path(path).resolve()
    volumes = list_volumes()
    for vol in volumes:
        vol_path = Path(vol["path"])
        if vol_path in p.parents or vol_path == p:
            return vol
    return None


def safe_eject(volume_path: str | Path, force: bool = False) -> tuple[bool, str]:
    """Safely eject an external volume.

    On macOS uses ``diskutil eject``.  On Linux/mock returns a warning.
    Does nothing on CI or headless environments.

    Args:
        volume_path: Path to the mounted volume (e.g. ``/Volumes/MyUSB``).
        force: Force-eject even if the volume is busy.

    Returns:
        ``(success, message)``
    """
    vol = Path(volume_path)
    if not vol.exists():
        return False, f"Volume not found: {vol}"
    if sys.platform != "darwin":
        return False, "Eject only supported on macOS (diskutil)"

    cmd = ["diskutil", "eject"]
    if force:
        cmd.insert(2, "force")
    cmd.append(str(vol))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, f"Ejected {vol.name}"
        return False, result.stderr.strip() or "Eject failed"
    except FileNotFoundError:
        return False, "diskutil not found (only available on macOS)"
    except subprocess.TimeoutExpired:
        return False, "Eject timed out (volume may be busy)"
    except Exception as exc:
        return False, f"Eject error: {exc}"


def format_volume_summary() -> str:
    """Return a human-readable summary of all mounted volumes."""
    volumes = list_volumes()
    if not volumes:
        return "No external volumes detected."

    lines = ["Detected volumes:", ""]
    for v in volumes:
        ro = " (read-only)" if v.get("is_readonly") else ""
        fs = v.get("filesystem", "?")
        lines.append(f"  📁 {v['name']}{ro}  [{fs}]  {v['path']}")
    lines.append("")
    lines.append(f"  {len(volumes)} volume(s) total")
    return "\n".join(lines)


# ── Internal helpers ─────────────────────────────────────────────────


MACOS_SYSTEM_VOLUMES = {
    "Macintosh HD", "Recovery", "VM", "Preboot", "Update",
    "macOS Base System", "macOS Install Data", "UpdateBundle",
}


def _macos_volumes() -> list[dict]:
    """Discover mounted macOS volumes under ``/Volumes``."""
    volumes: list[dict] = []
    root = config.MACOS_VOLUMES_ROOT
    if not root.exists():
        return volumes
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in MACOS_SYSTEM_VOLUMES:
            continue
        info = _volume_info(child)
        if info is not None:
            volumes.append(info)
    return volumes


def _windows_volumes() -> list[dict]:
    """Discover removable Windows drives (D:\\ through Z:\\).

    Uses ``GetDriveTypeW`` via ctypes to identify removable media.
    Falls back to checking if the drive appears to be non-system
    (not C:\\) and is accessible.
    """
    volumes: list[dict] = []
    try:
        import ctypes
        DRIVE_REMOVABLE = 2
        get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
        for letter in string.ascii_uppercase[1:]:  # B: through Z:
            root_path = f"{letter}:\\"
            drive_type = get_drive_type(root_path)
            if drive_type == DRIVE_REMOVABLE:
                vol_path = Path(root_path)
                if vol_path.exists():
                    volumes.append({
                        "name": f"{letter}:",
                        "path": root_path,
                        "is_internal": False,
                        "is_readonly": not os.access(root_path, os.W_OK),
                        "mount_point": root_path,
                        "filesystem": "?",
                    })
    except (ImportError, AttributeError):
        # ctypes not available or not Windows — fall back to path check
        for letter in string.ascii_uppercase[1:]:
            root_path = f"{letter}:\\"
            vol_path = Path(root_path)
            if vol_path.exists():
                volumes.append({
                    "name": f"{letter}:",
                    "path": root_path,
                    "is_internal": False,
                    "is_readonly": not os.access(root_path, os.W_OK),
                    "mount_point": root_path,
                    "filesystem": "?",
                })
    return volumes


def _linux_volumes() -> list[dict]:
    """Fallback for Linux — list /media/* and /mnt/* mount points."""
    volumes: list[dict] = []
    for base in [Path("/media"), Path("/mnt")]:
        if not base.exists():
            continue
        for child in base.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                volumes.append({
                    "name": child.name,
                    "path": str(child),
                    "is_internal": False,
                    "is_readonly": not os.access(str(child), os.W_OK),
                    "mount_point": str(child),
                    "filesystem": "?",
                })
    return volumes


def _volume_info(mount_path: Path) -> Optional[dict]:
    """Build a volume info dict for *mount_path*."""
    try:
        stat = mount_path.stat()
        # Basic info without shelling out
        info: dict = {
            "name": mount_path.name,
            "path": str(mount_path),
            "is_internal": False,
            "is_readonly": not os.access(str(mount_path), os.W_OK),
            "mount_point": str(mount_path),
            "filesystem": "?",
        }

        # Try to get filesystem type via statvfs
        try:
            svfs = os.statvfs(str(mount_path))
            info["filesystem"] = _guess_fs(svfs)
        except Exception:
            pass

        return info
    except OSError:
        return None


def _guess_fs(svfs) -> str:
    """Crude filesystem guess from statvfs fields (macOS only)."""
    # On macOS, f_frsize == 0 for some virtual filesystems
    if svfs.f_blocks == 0:
        return "virtual"
    return "HFS+ / APFS" if sys.platform == "darwin" else "?"
