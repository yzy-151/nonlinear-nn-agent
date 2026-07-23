import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PackageImportsTest(unittest.TestCase):
    def test_package_import_does_not_eagerly_import_torch(self):
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(PROJECT_ROOT / 'src')!r}); "
            "import nonlinear_agent; "
            "print('torch' in sys.modules)"
        )

        result = subprocess.run(
            [sys.executable, "-c", code],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
