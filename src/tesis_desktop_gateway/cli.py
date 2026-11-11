from __future__ import annotations

import argparse
from pathlib import Path

from tesis_desktop_gateway.server import GatewayServer


def main() -> None:
    parser = argparse.ArgumentParser(prog="tesis-desktop-gateway")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--template-root", type=Path)
    arguments = parser.parse_args()
    GatewayServer(arguments.workspace, template_root=arguments.template_root).serve()


if __name__ == "__main__":
    main()
