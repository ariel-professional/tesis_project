from pathlib import Path

from tesis_domain_extensions.schema_generation import write_all_domain_schemas


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "domain_schemas"
    write_all_domain_schemas(destination)


if __name__ == "__main__":
    main()
