"""Canonical supported languages for user profiles.

Codes are ISO 639-1 two-letter codes where available; the list prioritises
languages with large speaker bases (native + second-language) and adds
coverage for major European languages.
"""

SUPPORTED_LANGUAGES: dict[str, str] = {
    # Top global languages by total speakers
    "en": "English",
    "zh": "Chinese (Mandarin)",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "ar": "Arabic",
    "bn": "Bengali",
    "pt": "Portuguese",
    "ru": "Russian",
    "ur": "Urdu",
    "id": "Indonesian",
    "de": "German",
    "ja": "Japanese",
    "mr": "Marathi",
    "te": "Telugu",
    "tr": "Turkish",
    "ta": "Tamil",
    "vi": "Vietnamese",
    "ko": "Korean",
    "it": "Italian",
    "gu": "Gujarati",
    "pl": "Polish",
    "uk": "Ukrainian",
    "fa": "Persian",
    "ml": "Malayalam",
    "kn": "Kannada",
    "or": "Odia",
    "my": "Burmese",
    "th": "Thai",
    "ms": "Malay",
    "pa": "Punjabi",
    "tl": "Tagalog",
    "sw": "Swahili",
    # Major European languages
    "nl": "Dutch",
    "ro": "Romanian",
    "az": "Azerbaijani",
    "kk": "Kazakh",
    "sv": "Swedish",
    "cs": "Czech",
    "el": "Greek",
    "hu": "Hungarian",
    "sr": "Serbian",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "hr": "Croatian",
    "da": "Danish",
    "fi": "Finnish",
    "sk": "Slovak",
    "no": "Norwegian",
    "sq": "Albanian",
    "lt": "Lithuanian",
    "sl": "Slovenian",
    "lv": "Latvian",
    "et": "Estonian",
    "be": "Belarusian",
    "bs": "Bosnian",
    "mk": "Macedonian",
    "mt": "Maltese",
    "ga": "Irish",
    "cy": "Welsh",
    "is": "Icelandic",
    "ka": "Georgian",
    "hy": "Armenian",
    "he": "Hebrew",
    "eu": "Basque",
    "gl": "Galician",
    "lb": "Luxembourgish",
}

SUPPORTED_LANGUAGE_CODES: set[str] = set(SUPPORTED_LANGUAGES)

MAX_LANGUAGES = 10
MAX_LANGUAGE_CODE_LENGTH = 3
