"""Exercise the real launcher control flow with mocked Linux device commands.

No real block devices, mounts, privileges, or Calamares are used.
Run: python3 -m unittest discover -s tests -v
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("APHRODITE_OS_TEST_SCRIPT", str(
    ROOT / "config/includes.chroot/opt/aphrodite-os-installer-build/usr/libexec/"
    "aphrodite-os-protect-medium"
)))
SHELL = os.environ.get("APHRODITE_OS_TEST_SHELL") or shutil.which("sh")
if not SHELL and os.name == "nt":
    candidate = Path(r"C:\Program Files\Git\bin\bash.exe")
    if candidate.is_file():
        SHELL = str(candidate)


def command_mock(name, responses):
    clauses = []
    for args, output in responses.items():
        if isinstance(output, tuple):
            text, status = output
            clauses.append(f"{shlex.quote(args)}) printf '%s\\n' {shlex.quote(text)}; return {status} ;;")
            continue
        clauses.append(f"{shlex.quote(args)}) printf '%s\\n' {shlex.quote(output)} ;;")
    return (f'{name}() {{ case "$*" in\n' + "\n".join(clauses) +
            '\n*) return 1 ;;\nesac; }\n')


@unittest.skipUnless(SHELL, "POSIX shell required")
class ProtectMediumTests(unittest.TestCase):
    def run_fixture(self, live_id, mapping, ancestors, children, *, backing=None,
                    blocks=None, listing_error=False, ventoy_id=None, mode="--mask",
                    device_numbers=None):
        responses = {"-nrpo PATH,MAJ:MIN": (mapping, 1) if listing_error else mapping}
        responses.update({f"-snrpo PATH,TYPE {path}": value
                          for path, value in ancestors.items()})
        responses.update({f"-nrpo PATH {path}": value
                          for path, value in children.items()})
        if blocks is None:
            blocks = [line.split()[0] for line in mapping.splitlines() if line.strip()]
        patterns = "|".join(shlex.quote(path) for path in blocks) or "__no_device__"
        harness = f'''test() {{
    if [ "$1" = -b ]; then
        case "$2" in {patterns}) return 0 ;; *) return 1 ;; esac
    fi
    command test "$@"
}}
mount() {{ printf 'MASK %s\\n' "$3"; }}
'''
        harness += command_mock("lsblk", responses)
        nodes = dict(line.split() for line in mapping.splitlines() if line.strip())
        nodes.update(device_numbers or {})
        harness += command_mock("stat", {f"-Lc %Hr:%Lr -- {path}": number
                                         for path, number in nodes.items()})
        harness += command_mock("findmnt", {} if live_id is None else {
            "-rn -o MAJ:MIN --mountpoint /run/live/medium": live_id})
        harness += command_mock("losetup", {
            f"--list --noheadings --raw --output BACK-MAJ:MIN {path}": value
            for path, value in (backing or {}).items()})
        source = SCRIPT.read_text(encoding="utf-8")
        ventoy_call = '/usr/bin/python3 /usr/libexec/aphrodite-os-ventoy-device "$major_minor"'
        self.assertEqual(source.count(ventoy_call), 1)
        source = source.replace(ventoy_call, 'ventoy_device "$major_minor"')
        harness += command_mock("ventoy_device", {} if ventoy_id is None else {
            live_id: ventoy_id})
        return subprocess.run([SHELL, "-s", "--", mode], input=harness + source,
                              text=True, capture_output=True, timeout=10)

    def assert_masked(self, result, devices):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [f"MASK {path}" for path in sorted(devices)])

    def assert_stopped(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("MASK ", result.stdout)
        self.assertIn("Unable to identify the disk backing", result.stderr)

    def test_identify_reports_ventoy_disk_without_masking(self):
        result = self.run_fixture(
            "254:0", "/dev/sda 8:0\n/dev/sdb 8:16",
            {"/dev/sdb": "/dev/sdb disk"}, {}, ventoy_id="8:16", mode="--identify")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "/dev/sdb\n")

    def test_missing_protected_child_aborts_before_masking(self):
        result = self.run_fixture(
            "8:17", "/dev/sdb 8:16\n/dev/sdb1 8:17",
            {"/dev/sdb1": "/dev/sdb1 part\n/dev/sdb disk"},
            {"/dev/sdb": "/dev/sdb\n/dev/sdb1\n/dev/sdb2"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("/dev/sdb2 is no longer a block device", result.stderr)

    def test_optical_medium_without_dev_block_alias(self):
        result = self.run_fixture("11:0", "/dev/sr0 11:0\n/dev/sda 8:0",
                                  {"/dev/sr0": "/dev/sr0 rom"},
                                  {"/dev/sr0": "/dev/sr0"})
        self.assert_masked(result, ["/dev/sr0"])

    def test_usb_partition_hides_disk_and_all_partitions(self):
        result = self.run_fixture(
            "8:17", "/dev/sda 8:0\n/dev/sdb 8:16\n/dev/sdb1 8:17\n/dev/sdb2 8:18",
            {"/dev/sdb1": "/dev/sdb1 part\n/dev/sdb disk"},
            {"/dev/sdb": "/dev/sdb\n/dev/sdb1\n/dev/sdb2"})
        self.assert_masked(result, ["/dev/sdb", "/dev/sdb1", "/dev/sdb2"])

    def test_nvme_partition(self):
        result = self.run_fixture(
            "259:1", "/dev/nvme0n1 259:0\n/dev/nvme0n1p1 259:1",
            {"/dev/nvme0n1p1": "/dev/nvme0n1p1 part\n/dev/nvme0n1 disk"},
            {"/dev/nvme0n1": "/dev/nvme0n1\n/dev/nvme0n1p1"})
        self.assert_masked(result, ["/dev/nvme0n1", "/dev/nvme0n1p1"])

    def test_hidden_ventoy_mapping_protects_real_usb_and_partitions(self):
        result = self.run_fixture(
            "254:0", "/dev/sda 8:0\n/dev/sdb 8:16\n/dev/sdb1 8:17\n/dev/sdb2 8:18",
            {"/dev/sdb": "/dev/sdb disk"},
            {"/dev/sdb": "/dev/sdb\n/dev/sdb1\n/dev/sdb2"}, ventoy_id="8:16")
        self.assert_masked(result, ["/dev/sdb", "/dev/sdb1", "/dev/sdb2"])

    def test_ventoy_fallback_rejects_unresolvable_disk(self):
        self.assert_stopped(self.run_fixture(
            "254:0", "/dev/sda 8:0", {}, {}, ventoy_id="8:16"))

    def test_ventoy_fallback_rejects_multiple_device_ids(self):
        self.assert_stopped(self.run_fixture(
            "254:0", "/dev/sda 8:0\n/dev/sdb 8:16", {}, {},
            ventoy_id="8:0\n8:16"))

    def test_loop_backed_iso_traces_backing_device(self):
        result = self.run_fixture(
            "7:0", "/dev/loop0 7:0\n/dev/sdb 8:16\n/dev/sdb1 8:17",
            {"/dev/loop0": "/dev/loop0 loop",
             "/dev/sdb1": "/dev/sdb1 part\n/dev/sdb disk"},
            {"/dev/sdb": "/dev/sdb\n/dev/sdb1"},
            backing={"/dev/loop0": "8:17"})
        self.assert_masked(result, ["/dev/sdb", "/dev/sdb1"])

    def test_nested_loop_backed_iso(self):
        result = self.run_fixture(
            "7:0", "/dev/loop0 7:0\n/dev/loop1 7:1\n/dev/sdb 8:16",
            {"/dev/loop0": "/dev/loop0 loop",
             "/dev/loop1": "/dev/loop1 loop", "/dev/sdb": "/dev/sdb disk"},
            {"/dev/sdb": "/dev/sdb"},
            backing={"/dev/loop0": "7:1", "/dev/loop1": "8:16"})
        self.assert_masked(result, ["/dev/sdb"])

    def test_multiple_backing_disks_are_both_protected(self):
        result = self.run_fixture(
            "253:0", "/dev/dm-0 253:0\n/dev/sda 8:0\n/dev/sdb 8:16",
            {"/dev/dm-0": "/dev/dm-0 crypt\n/dev/sda disk\n/dev/sdb disk"},
            {"/dev/sda": "/dev/sda", "/dev/sdb": "/dev/sdb"})
        self.assert_masked(result, ["/dev/sda", "/dev/sdb"])

    def test_missing_mount_stops_before_masking(self):
        self.assert_stopped(self.run_fixture(None, "", {}, {}))

    def test_unresolved_id_stops_before_masking(self):
        self.assert_stopped(self.run_fixture("11:0", "/dev/sda 8:0", {}, {}))

    def test_failed_listing_with_partial_output_stops_before_masking(self):
        self.assert_stopped(self.run_fixture(
            "11:0", "/dev/sr0 11:0", {}, {}, listing_error=True))

    def test_stale_device_node_stops_before_masking(self):
        self.assert_stopped(self.run_fixture("11:0", "/dev/sr0 11:0", {}, {}, blocks=[]))

    def test_mismatched_device_node_number_stops(self):
        self.assert_stopped(self.run_fixture(
            "11:0", "/dev/sr0 11:0", {"/dev/sr0": "/dev/sr0 rom"},
            {"/dev/sr0": "/dev/sr0"}, device_numbers={"/dev/sr0": "11:1"}))

    def test_ambiguous_mapping_stops_before_masking(self):
        self.assert_stopped(self.run_fixture(
            "11:0", "/dev/sr0 11:0\n/dev/sr1 11:0", {}, {}))

    def test_nonphysical_loop_backing_stops_before_masking(self):
        self.assert_stopped(self.run_fixture(
            "7:0", "/dev/loop0 7:0", {"/dev/loop0": "/dev/loop0 loop"}, {},
            backing={"/dev/loop0": "0:42"}))

    def test_loop_cycle_stops_before_masking(self):
        self.assert_stopped(self.run_fixture(
            "7:0", "/dev/loop0 7:0", {"/dev/loop0": "/dev/loop0 loop"}, {},
            backing={"/dev/loop0": "7:0"}))

    def test_malformed_device_ids_fail_closed(self):
        for live_id in ("", "11", ":0", "11:", "11:0:1", "x:0", "11:0\n8:0"):
            with self.subTest(live_id=live_id):
                self.assert_stopped(self.run_fixture(live_id, "/dev/sr0 11:0", {}, {}))


if __name__ == "__main__":
    unittest.main()
