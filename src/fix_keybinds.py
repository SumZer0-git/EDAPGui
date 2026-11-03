"""Console tool: fills gaps and resolves conflicts in the Elite Dangerous keybindings EDAP needs.

Works on the .binds files, so Elite Dangerous must not be running. Every change is shown and has to be confirmed.
"""

from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path

from game.binds_files import GENERAL, SHIP, preset_names
from game.keybind_fixer import (
    CONFLICT,
    GAP,
    HOTKEY,
    NO_KEY_FOUND,
    REPLACE,
    SLOTS,
    UNKNOWN_KEY,
    BindsFile,
    Change,
    apply_changes,
    build_plan,
    is_game_running,
    load_active_files,
    write_file,
)

TEXTS = {
    "de": {
        "running": "Elite Dangerous läuft. Bitte das Spiel beenden, weil es die Tastenbelegung beim Beenden "
        "überschreiben kann.",
        "no_start": "StartPreset.4.start oder eine dort genannte .binds-Datei wurde nicht gefunden. Bitte im Spiel "
        "einmal die Steuerung öffnen und speichern.",
        "files": "Aktive Belegungen:",
        "builtin": "{category}: Voreinstellung '{name}' ist ein eingebautes Preset ohne Datei und kann nicht "
        "geändert werden. Bitte im Spiel auf DopeEx (oder ein eigenes Preset) umstellen, sonst fehlen die "
        "Tasten für EDAP.",
        GENERAL: "Allgemeine Steuerung",
        SHIP: "Schiffssteuerung",
        "layout": "Tastaturlayout",
        "ok": "Alles in Ordnung, es gibt nichts zu ändern.",
        "notes": "Hinweise (werden nicht geändert):",
        HOTKEY: "{action}: liegt auf {old}, einem EDAP-Hotkey. Bitte im Spiel auf eine andere Taste legen.",
        UNKNOWN_KEY: "{action}: die Taste '{old}' ist für das Layout {layout} unbekannt und wird übersprungen.",
        NO_KEY_FOUND: "{action}: es wurde keine freie Taste gefunden. Bitte im Spiel belegen.",
        GAP: "LÜCKE: keine Tastaturbelegung",
        REPLACE: "KEIN FREIER PLATZ: überschreibt eine Belegung eines anderen Geräts",
        CONFLICT: "KONFLIKT: Taste ist doppelt belegt mit {partners}",
        "default": "Standard-Voreinstellung von Elite",
        "preferred": "Vorschlag von EDAP (einzelne Taste, ohne Modifier)",
        "fallback": "Vorschlag von EDAP (einzelne Taste, ohne Modifier)",
        "change": "[{n}/{total}] {action} ({category}, {file})",
        "slot": "    {slot}: {old}  ->  {new}   [{source}]",
        "empty": "(leer)",
        "current": "    Aktuell: {slot}: {value}",
        "newkey": "    Neue Taste: {new}   [{source}]",
        "replace_prompt": "    Welchen Platz ?berschreiben? [1] Primary / [2] Secondary / [N]ein / [K]eine weiteren / "
        "[Q]uit: ",
        "prompt": "    Übernehmen? [J]a / [N]ein / [A]lle Lücken übernehmen / [K]eine weiteren / [Q]uit: ",
        "nothing": "Keine Änderungen übernommen.",
        "written": "Geschrieben: {file} ({count} Änderungen). Sicherung: {backup}",
        "failed": "Fehler bei {file}: {error} Die Datei wurde nicht verändert.",
        "dry": "Nur Vorschau (--dry-run), es wird nichts geschrieben.",
        "yes_skip": "Übersprungen (nur mit Rückfrage): {action}",
        "done": "Fertig. Beim nächsten Spielstart gelten die neuen Tasten.",
    },
    "en": {
        "running": "Elite Dangerous is running. Please close the game, because it can overwrite the keybindings "
        "when it exits.",
        "no_start": "StartPreset.4.start or a .binds file it names was not found. Open the controls in the game "
        "once and save them.",
        "files": "Active bindings:",
        "builtin": "{category}: the preset '{name}' is built into the game, has no file and cannot be changed. "
        "Please switch to DopeEx (or a custom preset) in the game, otherwise EDAP lacks its keys.",
        GENERAL: "General controls",
        SHIP: "Ship controls",
        "layout": "Keyboard layout",
        "ok": "Everything is fine, nothing to change.",
        "notes": "Notes (not changed):",
        HOTKEY: "{action}: is on {old}, an EDAP hotkey. Please move it to another key in the game.",
        UNKNOWN_KEY: "{action}: the key '{old}' is unknown for the layout {layout} and is skipped.",
        NO_KEY_FOUND: "{action}: no free key was found. Please bind it in the game.",
        GAP: "GAP: no keyboard binding",
        REPLACE: "NO FREE SLOT: overwrites a binding of another device",
        CONFLICT: "CONFLICT: key is also used by {partners}",
        "default": "Elite default preset",
        "preferred": "EDAP suggestion (single key, no modifier)",
        "fallback": "EDAP suggestion (single key, no modifier)",
        "change": "[{n}/{total}] {action} ({category}, {file})",
        "slot": "    {slot}: {old}  ->  {new}   [{source}]",
        "empty": "(empty)",
        "current": "    Current: {slot}: {value}",
        "newkey": "    New key: {new}   [{source}]",
        "replace_prompt": "    Which slot to overwrite? [1] Primary / [2] Secondary / [N]o / [S]kip the rest / "
        "[Q]uit: ",
        "prompt": "    Apply? [Y]es / [N]o / [A]ll gaps / [S]kip the rest / [Q]uit: ",
        "nothing": "No changes applied.",
        "written": "Written: {file} ({count} changes). Backup: {backup}",
        "failed": "Error in {file}: {error} The file was not changed.",
        "dry": "Preview only (--dry-run), nothing is written.",
        "yes_skip": "Skipped (needs confirmation): {action}",
        "done": "Done. The new keys apply the next time the game starts.",
    },
}


def detect_language() -> str:
    try:
        return "de" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF == 0x07 else "en"
    except (AttributeError, OSError):
        return "en"


def ask(texts: dict[str, str], change: Change) -> str:
    """Returns "yes", "no", "all", "skip" or "quit"."""
    default = "yes" if change.kind == GAP else "no"
    replace = change.kind == REPLACE
    while True:
        try:
            answer = input(texts["replace_prompt" if replace else "prompt"]).strip().lower()
        except EOFError:
            return "quit"
        if not answer:
            return default
        if replace and answer[0] in "12":
            change.slot = SLOTS[int(answer[0]) - 1]
            change.old = change.current.get(change.slot, "")
            return "yes"
        if replace and answer[0] in "aj":
            continue
        choices = {"j": "yes", "y": "yes", "n": "no", "a": "all", "k": "skip", "s": "skip", "q": "quit"}
        if answer[0] in choices:
            return choices[answer[0]]


def show_change(texts: dict[str, str], change: Change, number: int, total: int) -> None:
    category = texts[change.category]
    print()
    print(
        texts["change"].format(
            n=number, total=total, action=change.action, category=category, file=change.file.path.name
        )
    )
    print("    " + texts[change.kind].format(partners=", ".join(change.partners)))
    for slot, value in change.current.items():
        print(texts["current"].format(slot=slot, value=value or texts["empty"]))
    if change.kind == REPLACE:
        print(texts["newkey"].format(new=change.new, source=texts[change.source]))
        return
    print(
        texts["slot"].format(
            slot=change.slot,
            old=change.old or texts["empty"],
            new=change.new,
            source=texts[change.source],
        )
    )


def choose(texts: dict[str, str], changes: list[Change], assume_yes: bool) -> list[Change]:
    accepted = []
    accept_gaps = assume_yes
    for number, change in enumerate(changes, 1):
        if accept_gaps and change.kind == GAP:
            show_change(texts, change, number, len(changes))
            accepted.append(change)
            continue
        if assume_yes:
            print(texts["yes_skip"].format(action=change.action))
            continue
        show_change(texts, change, number, len(changes))
        answer = ask(texts, change)
        if answer == "all":
            accept_gaps = True
            answer = "yes"
        if answer == "yes":
            accepted.append(change)
        elif answer in ("skip", "quit"):
            break
    return accepted


def write_changes(texts: dict[str, str], accepted: list[Change]) -> int:
    by_file: dict[BindsFile, list[Change]] = {}
    for change in accepted:
        by_file.setdefault(change.file, []).append(change)
    status = 0
    for file, changes in by_file.items():
        try:
            backup = write_file(file, apply_changes(file, changes))
        except (OSError, ValueError) as error:
            print(texts["failed"].format(file=file.path.name, error=error))
            status = 1
            continue
        print(texts["written"].format(file=file.path.name, count=len(changes), backup=backup.name))
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="only show what would change")
    parser.add_argument("--yes", action="store_true", help="fill gaps without asking; conflicts are skipped")
    parser.add_argument("--lang", choices=sorted(TEXTS), default=detect_language())
    parser.add_argument("--bindings-dir", type=Path, help="folder with the .binds files (default: the game's)")
    args = parser.parse_args(argv)
    texts = TEXTS[args.lang]

    if not args.dry_run and is_game_running():
        print(texts["running"])
        return 1
    files = load_active_files(args.bindings_dir)
    if not files:
        print(texts["no_start"])
        return 1

    print(texts["files"])
    for category, file in files.items():
        print(f"  {texts[category]}: {file.path.name} ({texts['layout']}: {file.layout or '?'})")
    for category, name in preset_names(args.bindings_dir).items():
        if category not in files:
            print("  " + texts["builtin"].format(category=texts[category], name=name))

    plan = build_plan(files)
    if plan.notes:
        print()
        print(texts["notes"])
        for note in plan.notes:
            file_slot = note.file.effective_slot(note.action)
            old = note.detail or (file_slot[1].describe() if file_slot else "")
            print("  " + texts[note.kind].format(action=note.action, old=old, layout=note.file.layout or "en-US"))
    if not plan.changes:
        print()
        print(texts["ok"])
        return 0

    if args.dry_run:
        print()
        print(texts["dry"])
        for number, change in enumerate(plan.changes, 1):
            show_change(texts, change, number, len(plan.changes))
        return 0

    accepted = choose(texts, plan.changes, args.yes)
    print()
    if not accepted:
        print(texts["nothing"])
        return 0
    status = write_changes(texts, accepted)
    print(texts["done"])
    return status


if __name__ == "__main__":
    sys.exit(main())
