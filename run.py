import os, sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
os.chdir(str(_root))
sys.path.insert(0, str(_root))

from src.api.server import main

if __name__ == "__main__":
    port = os.environ.get("PORT", "20100")
    host = os.environ.get("HOST", "0.0.0.0")
    os.environ.setdefault("PORT", str(port))
    os.environ.setdefault("HOST", str(host))
    print(f"[anisama] API starting on http://{host}:{port}")
    print(f"[anisama] Docs at http://{host}:{port}/")
    main()
