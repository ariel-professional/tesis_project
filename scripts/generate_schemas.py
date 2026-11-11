from pathlib import Path

from tesis_proyect.schema_generation import write_schemas


def main() -> None:
    write_schemas(Path(__file__).resolve().parents[1] / "schemas" / "1.0.0")


if __name__ == "__main__":
    main()
