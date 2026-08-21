import importlib.util
import subprocess
import sys


def ensure_dependencies() -> None:
    packages = [
        "PyQt6",
        "curl_cffi",
        "selectolax",
        "aiofiles",
        "aiosqlite",
        "psutil",
    ]
    missing = [p for p in packages if importlib.util.find_spec(p) is None]
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])