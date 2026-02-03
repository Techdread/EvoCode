"""Language ID mappings for Judge0."""

# Judge0 language IDs
# Based on judge0-setup/verify_judge0.py and Judge0 CE documentation
LANGUAGE_IDS = {
    # Common languages
    "python": 71,      # Python 3.8.1
    "python3": 71,
    "javascript": 63,  # Node.js 12.14.0
    "js": 63,
    "node": 63,
    "typescript": 74,  # TypeScript 3.7.4
    "ts": 74,

    # Compiled languages
    "c": 50,           # GCC 9.2.0
    "cpp": 54,         # GCC 9.2.0
    "c++": 54,
    "java": 62,        # OpenJDK 13.0.1
    "rust": 73,        # Rust 1.40.0
    "go": 60,          # Go 1.13.5
    "golang": 60,

    # Other languages
    "ruby": 72,        # Ruby 2.7.0
    "php": 68,         # PHP 7.4.1
    "csharp": 51,      # Mono 6.6.0.161
    "c#": 51,
    "swift": 83,       # Swift 5.2.3
    "kotlin": 78,      # Kotlin 1.3.70
    "scala": 81,       # Scala 2.13.2

    # Scripting languages
    "bash": 46,        # Bash 5.0.0
    "shell": 46,
    "perl": 85,        # Perl 5.28.1
    "lua": 64,         # Lua 5.3.5
    "r": 80,           # R 4.0.0

    # Functional languages
    "haskell": 61,     # GHC 8.8.1
    "clojure": 86,     # Clojure 1.10.1
    "elixir": 57,      # Elixir 1.9.4
    "erlang": 58,      # Erlang OTP 22.2
    "fsharp": 87,      # F# .NET Core 3.1.202
    "f#": 87,
    "ocaml": 65,       # OCaml 4.09.0

    # Other
    "fortran": 59,     # Fortran GFortran 9.2.0
    "pascal": 67,      # Free Pascal 3.0.4
    "cobol": 77,       # COBOL GnuCOBOL 2.2
    "vbnet": 84,       # VB.NET Mono 6.6.0.161
    "assembly": 45,    # Assembly NASM 2.14.02
    "sql": 82,         # SQLite 3.27.2
    "plaintext": 43,   # Plain Text
}

# Reverse mapping for display
LANGUAGE_NAMES = {v: k for k, v in LANGUAGE_IDS.items()}

# Clean display names
DISPLAY_NAMES = {
    71: "Python 3",
    63: "JavaScript (Node.js)",
    74: "TypeScript",
    50: "C (GCC)",
    54: "C++ (GCC)",
    62: "Java",
    73: "Rust",
    60: "Go",
    72: "Ruby",
    68: "PHP",
    51: "C# (Mono)",
    83: "Swift",
    78: "Kotlin",
    81: "Scala",
    46: "Bash",
    85: "Perl",
    64: "Lua",
    80: "R",
    61: "Haskell",
    86: "Clojure",
    57: "Elixir",
    58: "Erlang",
    87: "F#",
    65: "OCaml",
    59: "Fortran",
    67: "Pascal",
    77: "COBOL",
    84: "VB.NET",
    45: "Assembly (NASM)",
    82: "SQLite",
    43: "Plain Text",
}


def get_language_id(language: str) -> int:
    """Get Judge0 language ID from language name."""
    lang_lower = language.lower().strip()
    if lang_lower in LANGUAGE_IDS:
        return LANGUAGE_IDS[lang_lower]
    raise ValueError(f"Unknown language: {language}. Available: {list(set(LANGUAGE_IDS.values()))}")


def get_language_name(language_id: int) -> str:
    """Get display name from Judge0 language ID."""
    return DISPLAY_NAMES.get(language_id, f"Unknown ({language_id})")


def get_supported_languages() -> list[dict]:
    """Get list of supported languages with their IDs."""
    seen = set()
    languages = []
    for name, lang_id in sorted(LANGUAGE_IDS.items()):
        if lang_id not in seen:
            seen.add(lang_id)
            languages.append({
                "id": lang_id,
                "name": name,
                "display_name": DISPLAY_NAMES.get(lang_id, name),
            })
    return sorted(languages, key=lambda x: x["display_name"])
