# Game languages and language packs

The application interface remains English. **Settings > Game language** controls game-text recognition and the
default commodity-name language, not the GUI language.

## Selection

- **Auto** reads the `language` field in the latest game journal header. It checks again between assist runs, so
  restarting Elite Dangerous in another language does not require restarting EDAPGui.
  An empty or partially written new journal is allowed up to 15 seconds for its header before English fallback
  is reported. No assist starts and no OCR model is replaced during that wait. A complete record without a
  language header ends the wait immediately; no journal, a missing language, or an unsupported language still
  produces a warning. A header arriving after the timeout is picked up on a later check.
- A named language overrides journal detection.
- If the journal language cannot be determined or its pack is not installed, EDAPGui warns and attempts English.
  This does not make English text match a different game language. Switch the game to a supported language if
  recognition fails.
- A pack with an unsupported OCR language also falls back to English with a warning. A model initialization or
  download failure is reported; assists do not run using a mismatched old model. Change the selection or restart
  EDAPGui after resolving that failure.
- Changes are applied between assists, never by replacing an OCR engine during an input sequence. Repeated OCR
  reads, timeouts, dialog confirmation and transaction verification remain in place.

The single configuration key is `Language`, containing `auto` or a language-folder name such as `de` or `en`.
Existing explicit selections are retained. The obsolete `OCRLanguage` setting is ignored and removed from the
in-memory configuration; the next settings save writes the configuration without it. OCR settings now belong to
the language pack.

English and German are bundled. Only the active language's text variants are compared; missing recognition entries
fall back to English with a warning. `CARTOGRAPHICS` is a language-independent logo, not a translated header.

## Adding a language

Contribute language files through a pull request, or attach them to a project issue if you do not work with Git.
No Python changes or registration in a hard-coded language list are needed.

Create a folder such as `assets/locales/fr/` containing:

### `language.json`

```json
{
    "name": "French",
    "journal_languages": ["French/FR"],
    "ocr_language": "fr"
}
```

The folder name is the stored language code. `auto` is reserved. Use a unique display name and the exact language
strings emitted by the game journal; aliases must not overlap another pack. The `ocr_language` must be supported
by the project's pinned PaddleOCR version. It need not equal the folder name. A different OCR model may require
a download on first use; ordinary text recognition runs locally.

### `recognition.json`

Copy the keys from the English file and replace the values with the actual game text, not a free translation.
The key order does not matter. One value may be a string or a list of genuine alternatives:

```json
{
    "ALIGN_WITH_TARGET_MSG": ["FIRST GAME TEXT", "ALTERNATIVE GAME TEXT"]
}
```

Partial files are accepted with explicit English fallback warnings. Empty values, placeholder `?` values,
unknown keys and duplicate JSON keys are errors, not working translations. Invalid additional packs are reported
and excluded from the selector without preventing the valid packs from loading. The English base pack is required.

### `commodities.json`

Map the game's numeric commodity IDs to exact localized names:

```json
{
    "128049152": "Platine"
}
```

Copy IDs from `data/commodities.json`; do not change IDs or create new commodities just to add names. Partial
translations are supported: missing names display in English with a warning. An omitted commodities file has the
same effect as an empty translation. The central catalogue holds identity, symbol and rarity, not translated names.

Restart EDAPGui after adding or editing packs. The Settings selector discovers valid folders at startup.

## Commodity identity and trading

Waypoint v2 trade lists and their separate progress files use commodity IDs as keys. Their stored order remains
the editor's trade priority. A language change changes display names, not which commodity the route requests.

The language catalogue is an offline editing aid. At trade time the ID must match an entry in the current market;
the game's own localized market name is used for dialog OCR. An English display fallback is never substituted for
an unavailable market identity. Stock, demand, cargo limits and game-confirmed transactions still determine what
can be traded and which remaining quantities are reduced.

The copied Inara text importer still accepts German and English input. Its target commodity language can come
from any installed pack; route identity itself is language-independent.

## Validation before contributing

Check the full game workflows affected by a pack, including navigation tabs, internal inventory tabs, station
services, jump alignment, disengagement and buy/sell dialogs. Text length can affect capture regions; market
sorting can differ by language. A syntactically valid pack is not a guarantee of correct OCR.

Test at 1080p SDR and 2160p HDR, with the default orange HUD and a custom HUD scheme. Include negative cases:
wrong commodity, wrong buy/sell direction, unrelated HUD messages and unreadable text must not confirm an action.
Keep raw screenshots local; do not attach full-screen captures containing player information to public issues or PRs.
Right-panel recognition checks only the unique filled tab highlight, not neighboring tab labels. Home and playlist
use their icon positions; text tabs still require an exact active-language match. The inventory tab must be
confirmed before carrier-transfer inputs are sent.
German uses `LAGERHALLEN` for the storage tab. Local screenshot regressions cover all eight right-panel tabs in
English and German with both HUD color schemes, including dense dark lettering on the orange highlight.
