"""Render an untrusted TGS in a resource-limited child process."""

import gzip
import json
import resource
import sys
from lottie.objects import Animation
from lottie.exporters.cairo import export_png


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    with gzip.open(sys.argv[1], "rb") as f:
        data = f.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("Expanded animation too large")
    obj = json.loads(data)
    if obj.get("assets"):
        raise ValueError("External animation assets are not supported")
    if obj.get("w", 0) > 2048 or obj.get("h", 0) > 2048:
        raise ValueError("Invalid dimensions")
    animation = Animation.load(obj)
    export_png(animation, sys.argv[2], frame=int(animation.in_point or 0))


if __name__ == "__main__":
    main()
