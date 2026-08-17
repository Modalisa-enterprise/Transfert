#!/usr/bin/env python3
"""Crée plusieurs archives ZIP à partir d'un dossier, avec une taille maximale par archive.

Exemple :
    python zip_packages.py /chemin/vers/dossier -o ./archives --max-size-mb 1900

Les fichiers ne sont jamais coupés : si un fichier seul dépasse la limite,
il est signalé et ignoré.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

DEFAULT_MAX_MB = 1900  # marge sous la limite GitHub de 2 Go


def human_size(size: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if size < 1024 or unit == "To":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size} o"


def archive_path(output: Path, base_name: str, part: int) -> Path:
    return output / f"{base_name}.part{part:03d}.zip"


def files_in(source: Path, output: Path):
    """Liste les fichiers sans réinclure les ZIP générés."""
    output_resolved = output.resolve()

    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue

        try:
            path.resolve().relative_to(output_resolved)
            continue
        except ValueError:
            pass

        yield path


def create_packages(
    source: Path,
    output: Path,
    max_size: int,
    compression: int
) -> int:
    output.mkdir(parents=True, exist_ok=True)

    base_name = source.name or "archive"
    part = 1
    estimated_size = 0
    written = 0
    skipped = []
    zf = None

    def open_part(number: int) -> zipfile.ZipFile:
        dest = archive_path(output, base_name, number)
        print(f"Création : {dest}")
        return zipfile.ZipFile(
            dest,
            mode="w",
            compression=compression,
            allowZip64=True
        )

    try:
        for file_path in files_in(source, output):
            file_size = file_path.stat().st_size
            relative_name = file_path.relative_to(source).as_posix()

            # Le fichier dépasse à lui seul la taille admise.
            if file_size > max_size:
                print(
                    f"ATTENTION : ignoré, trop grand : "
                    f"{relative_name} ({human_size(file_size)})",
                    file=sys.stderr,
                )
                skipped.append(file_path)
                continue

            # Fermer l'archive en cours et en créer une nouvelle si nécessaire.
            if zf is None or (
                estimated_size and estimated_size + file_size > max_size
            ):
                if zf is not None:
                    zf.close()
                    print(
                        f"  Terminé : "
                        f"{human_size(estimated_size)} de fichiers source\n"
                    )
                    part += 1

                zf = open_part(part)
                estimated_size = 0

            print(f"  + {relative_name} ({human_size(file_size)})")
            zf.write(file_path, arcname=relative_name)

            estimated_size += file_size
            written += 1

    finally:
        if zf is not None:
            zf.close()
            print(f"  Terminé : {human_size(estimated_size)}")

    print(f"\n{written} fichier(s) archivé(s) dans {part} archive(s).")

    if skipped:
        print(
            f"{len(skipped)} fichier(s) ignoré(s), car trop volumineux.",
            file=sys.stderr,
        )
        return 2

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Découpe le contenu d'un dossier en archives ZIP."
    )

    parser.add_argument(
        "source",
        type=Path,
        help="Dossier à archiver"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("zip_packages"),
        help="Dossier de destination"
    )

    parser.add_argument(
        "--max-size-mb",
        type=float,
        default=DEFAULT_MAX_MB,
        help="Taille maximale par ZIP en Mo (défaut : 1900)"
    )

    parser.add_argument(
        "--store",
        action="store_true",
        help="Ne pas compresser : plus rapide, taille exacte"
    )

    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    output = args.output.expanduser()

    if not source.is_dir():
        parser.error(f"Dossier source invalide : {source}")

    if args.max_size_mb <= 0:
        parser.error("--max-size-mb doit être supérieur à zéro.")

    max_size = int(args.max_size_mb * 1024 * 1024)

    compression = (
        zipfile.ZIP_STORED
        if args.store
        else zipfile.ZIP_DEFLATED
    )

    return create_packages(source, output, max_size, compression)


if __name__ == "__main__":
    raise SystemExit(main())