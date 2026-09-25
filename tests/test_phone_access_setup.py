#!/usr/bin/env python3
"""Temporary integration checks for the offline phone-access setup tool."""
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SETUP = REPO / "scripts" / "setup_phone_access.py"


class PhoneAccessSetupTest(unittest.TestCase):
    def test_setup_extend_and_conflict_preserve_credentials(self):
        with tempfile.TemporaryDirectory(prefix="gouda-phone-access-test-") as temp:
            output = Path(temp) / "phone-access"
            self.invoke("--hostname", "gouda.test", "--ip-address", "192.0.2.14",
                        "--output-dir", str(output))

            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            for name in ("ca.key", "tls.key", "token", "phone-access.json"):
                with self.subTest(private_file=name):
                    self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o600)

            self.assert_certificate(output, ["192.0.2.14"])
            original = self.hashes(output)
            protected = {name: original[name] for name in ("ca.crt", "ca.key", "token")}

            # A changed SAN on the default path is a conflict and leaves every
            # generated file byte-for-byte unchanged.
            failed = self.invoke(
                "--hostname", "gouda.test", "--ip-address", "198.51.100.7",
                "--output-dir", str(output), check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(self.hashes(output), original)

            # An explicit extension signs a new leaf with the existing CA and
            # retains the access token, so the iPhone does not need new trust.
            self.invoke(
                "--hostname", "gouda.test", "--ip-address", "198.51.100.7",
                "--extend-existing", "--output-dir", str(output),
            )
            extended = self.hashes(output)
            self.assertEqual({name: extended[name] for name in protected}, protected)
            self.assertNotEqual(extended["tls.crt"], original["tls.crt"])
            self.assertNotEqual(extended["tls.key"], original["tls.key"])
            self.assert_certificate(output, ["192.0.2.14", "198.51.100.7"])

            config = json.loads((output / "phone-access.json").read_text())
            self.assertEqual(config["url_ip_addresses"], ["192.0.2.14", "198.51.100.7"])
            self.assertEqual(
                config["gateway_arguments"][-6:],
                ["--allowed-host", "gouda.test",
                 "--allowed-host", "192.0.2.14",
                 "--allowed-host", "198.51.100.7"],
            )

            # Repeating the extension is idempotent.
            self.invoke(
                "--hostname", "gouda.test", "--ip-address", "198.51.100.7",
                "--extend-existing", "--output-dir", str(output),
            )
            self.assertEqual(self.hashes(output), extended)

    def invoke(self, *args, check=True):
        return subprocess.run(
            [sys.executable, str(SETUP), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def hashes(self, directory):
        return {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.iterdir())
            if path.is_file()
        }

    def assert_certificate(self, directory, addresses):
        cert = directory / "tls.crt"
        subprocess.run(
            ["openssl", "verify", "-CAfile", str(directory / "ca.crt"), str(cert)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        subprocess.run(
            ["openssl", "x509", "-in", str(cert), "-checkhost", "gouda.test", "-noout"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for address in addresses:
            subprocess.run(
                ["openssl", "x509", "-in", str(cert), "-checkip", address, "-noout"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )


if __name__ == "__main__":
    unittest.main()
