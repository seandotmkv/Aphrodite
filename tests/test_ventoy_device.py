"""Read-only Ventoy metadata regression tests; no real devices are accessed."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import stat
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "config/includes.chroot/opt/aphrodite-os-installer-build/usr/libexec/aphrodite-os-ventoy-device"
LOADER = SourceFileLoader("ventoy_device", str(SCRIPT))
MODULE = module_from_spec(spec_from_loader(LOADER.name, LOADER))
LOADER.exec_module(MODULE)
GUID = bytes(range(1, 17))
SIGNATURE = b"abcd"


def record(guid=GUID, signature=SIGNATURE, image=b"/aphrodite-os-0-amd64.iso"):
    data = bytearray(512)
    data[:16] = MODULE.MAGIC
    data[17:33] = guid
    data[45:45 + len(image)] = image
    struct.pack_into("<Q", data, 429, 2612176896)
    data[481:485] = signature
    data[16] = -sum(data) % 256
    return bytes(data)


def sector(guid=GUID, signature=SIGNATURE):
    data = bytearray(512)
    data[384:400] = guid
    data[440:444] = signature
    return bytes(data)


class VentoyDeviceTests(unittest.TestCase):
    def write(self, root, relative, data):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def test_decode_documented_format(self):
        self.assertEqual(MODULE.decode(record()),
                         (GUID, SIGNATURE, b"/aphrodite-os-0-amd64.iso", 2612176896))

    def test_bad_metadata_rejected(self):
        original = record()
        for data in (b"", original[:-1], original + b"x",
                     b"x" + original[1:], original[:500] + b"x" + original[501:],
                     record(guid=bytes(16)), record(image=b"relative.iso")):
            with self.subTest(data=data[:20]), self.assertRaises(ValueError):
                MODULE.decode(data)

    def test_saved_metadata_locations(self):
        for location in ("ventoy/ventoy_os_param",
                         "run/initramfs/ventoy/ventoy_os_param"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write(root, location, record())
                self.assertEqual(MODULE.boot_identity(root), MODULE.decode(record()))

    def test_uefi_variable_skips_attributes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "sys/firmware/efi/efivars/" + MODULE.EFI_NAME,
                       b"\x07\0\0\0" + record())
            self.assertEqual(MODULE.boot_identity(root), MODULE.decode(record()))

    def test_old_uefi_variable_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "sys/firmware/efi/vars/" + MODULE.EFI_NAME + "/data", record())
            self.assertEqual(MODULE.boot_identity(root), MODULE.decode(record()))

    def test_acpi_skips_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "sys/firmware/acpi/tables/VTOY", b"VTOY" + bytes(32) + record())
            self.assertEqual(MODULE.boot_identity(root), MODULE.decode(record()))

    def test_legacy_bios_bounded_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "dev/mem", bytes(0x80000 + 32) + record() + bytes(1024))
            self.assertEqual(MODULE.boot_identity(root), MODULE.decode(record()))

    def test_missing_metadata_stops(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(OSError):
            MODULE.boot_identity(Path(directory))

    def test_conflicting_metadata_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "ventoy/ventoy_os_param", record())
            self.write(root, "sys/firmware/efi/efivars/" + MODULE.EFI_NAME,
                       bytes(4) + record(guid=b"z" * 16))
            with self.assertRaises(ValueError):
                MODULE.boot_identity(root)

    def match(self, disks, sectors, modes=None, numbers=None):
        modes = modes or {}
        numbers = numbers or {}
        with patch.object(MODULE, "device_number", side_effect=str):
            return MODULE.matching_disk(
                MODULE.decode(record()), disks,
                read_sector=lambda path: sectors[path],
                get_stat=lambda path: SimpleNamespace(
                    st_mode=modes.get(path, stat.S_IFBLK),
                    st_rdev=numbers.get(path, next(d["maj:min"] for d in disks if d["path"] == path))))

    def disks(self):
        return [{"path": "/dev/sda", "type": "disk", "maj:min": "8:0"},
                {"path": "/dev/sdb", "type": "disk", "maj:min": "8:16"}]

    def test_matches_guid_and_signature_not_disk_order(self):
        self.assertEqual(self.match(self.disks(), {
            "/dev/sda": sector(guid=b"x" * 16), "/dev/sdb": sector()}), "8:16")

    def test_signature_must_also_match(self):
        with self.assertRaises(ValueError):
            self.match(self.disks(), {"/dev/sda": sector(signature=b"xxxx"),
                                      "/dev/sdb": sector(guid=b"x" * 16)})

    def test_duplicate_cloned_disk_identity_stops(self):
        with self.assertRaises(ValueError):
            self.match(self.disks(), {"/dev/sda": sector(), "/dev/sdb": sector()})

    def test_partition_is_never_used_as_whole_disk(self):
        with self.assertRaises(ValueError):
            self.match([{"path": "/dev/sdb1", "type": "part", "maj:min": "8:17"}], {})

    def test_stale_disk_listing_stops(self):
        with self.assertRaises(ValueError):
            self.match(self.disks(), {"/dev/sda": sector(), "/dev/sdb": sector()},
                       numbers={"/dev/sda": "8:32"})

    def test_regular_file_device_stops(self):
        with self.assertRaises(ValueError):
            self.match(self.disks(), {}, modes={"/dev/sda": stat.S_IFREG})

    def test_short_sector_stops(self):
        with self.assertRaises(ValueError):
            self.match(self.disks(), {"/dev/sda": b"short"})

    def test_mount_must_be_current_ventoy_iso(self):
        for output in ("/dev/sdb1 iso9660 254:0", "/dev/mapper/ventoy ext4 254:0",
                       "/dev/mapper/ventoy iso9660 253:0", ""):
            with self.subTest(output=output), patch.object(MODULE, "command", return_value=output):
                with self.assertRaises(ValueError):
                    MODULE.require_ventoy_mount("254:0")

    def test_ventoy_mount_matches_kernel_device_id(self):
        with patch.object(MODULE, "command", return_value="/dev/mapper/ventoy iso9660 254:0"), \
             patch.object(MODULE.os, "stat", return_value=SimpleNamespace(st_dev=1)), \
             patch.object(MODULE, "device_number", return_value="254:0"):
            MODULE.require_ventoy_mount("254:0")

    def test_changed_mount_stops(self):
        with patch.object(MODULE, "command", return_value="/dev/mapper/ventoy iso9660 254:0"), \
             patch.object(MODULE.os, "stat", return_value=SimpleNamespace(st_dev=1)), \
             patch.object(MODULE, "device_number", return_value="8:16"), self.assertRaises(ValueError):
            MODULE.require_ventoy_mount("254:0")


if __name__ == "__main__":
    unittest.main()
