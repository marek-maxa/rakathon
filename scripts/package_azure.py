"""Package only the current demo runtime and organizer-provided synthetic inputs."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [ROOT / "pyproject.toml", ROOT / "uv.lock"]
    files += [
        ROOT / "llm_intake" / name
        for name in (
            "__init__.py",
            "core.py",
            "client.py",
            "dialogue.py",
            "flow.py",
            "master.py",
            "master_contract.py",
            "pipeline.py",
            "question_catalog.py",
            "question_topics.json",
            "master_prompt.md",
            "master_schema.json",
            "master_examples.json",
            "prompt.md",
            "examples.json",
        )
    ]
    files += sorted((ROOT / "web").glob("*.py"))
    files += sorted((ROOT / "meddi").glob("*.py"))
    for directory in ("web/templates", "web/static"):
        files += sorted(
            path for path in (ROOT / directory).rglob("*") if path.is_file()
        )
    files += sorted((ROOT / "rakathon_meddi_onco_data/pacienti").glob("*.json"))
    files.append(ROOT / "rakathon_meddi_onco_data/docs/dotazniky_definice.json")
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
        if any(
            part.startswith(".") or part == "__pycache__"
            for part in path.relative_to(ROOT).parts
        ):
            raise ValueError(f"Unexpected deployment file: {path.name}")
    destination = ROOT / "dist/meddi-azure.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f"{destination}: {len(files)} files")


if __name__ == "__main__":
    main()
