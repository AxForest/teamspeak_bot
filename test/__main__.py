import unittest
from pathlib import Path

if __name__ == "__main__":
    loader = unittest.TestLoader()
    runner = unittest.TextTestRunner()

    # Run tests in main folder
    suite = loader.discover(str(Path(__file__).parent))
    runner.run(suite)

    for _ in Path(__file__).parent.iterdir():
        # Run tests in subfolders
        if _.is_dir() and (_ / "__init__.py").exists():
            suite = loader.discover(str(_))
            runner.run(suite)
