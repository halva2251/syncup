export interface Language {
  code: string;
  name: string;
}

export const SUPPORTED_LANGUAGES: Language[] = [
  // Top global languages by total speakers
  { code: "en", name: "English" },
  { code: "zh", name: "Chinese (Mandarin)" },
  { code: "hi", name: "Hindi" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "ar", name: "Arabic" },
  { code: "bn", name: "Bengali" },
  { code: "pt", name: "Portuguese" },
  { code: "ru", name: "Russian" },
  { code: "ur", name: "Urdu" },
  { code: "id", name: "Indonesian" },
  { code: "de", name: "German" },
  { code: "ja", name: "Japanese" },
  { code: "mr", name: "Marathi" },
  { code: "te", name: "Telugu" },
  { code: "tr", name: "Turkish" },
  { code: "ta", name: "Tamil" },
  { code: "vi", name: "Vietnamese" },
  { code: "ko", name: "Korean" },
  { code: "it", name: "Italian" },
  { code: "gu", name: "Gujarati" },
  { code: "pl", name: "Polish" },
  { code: "uk", name: "Ukrainian" },
  { code: "fa", name: "Persian" },
  { code: "ml", name: "Malayalam" },
  { code: "kn", name: "Kannada" },
  { code: "or", name: "Odia" },
  { code: "my", name: "Burmese" },
  { code: "th", name: "Thai" },
  { code: "ms", name: "Malay" },
  { code: "pa", name: "Punjabi" },
  { code: "tl", name: "Tagalog" },
  { code: "sw", name: "Swahili" },
  // Major European languages
  { code: "nl", name: "Dutch" },
  { code: "ro", name: "Romanian" },
  { code: "az", name: "Azerbaijani" },
  { code: "kk", name: "Kazakh" },
  { code: "sv", name: "Swedish" },
  { code: "cs", name: "Czech" },
  { code: "el", name: "Greek" },
  { code: "hu", name: "Hungarian" },
  { code: "sr", name: "Serbian" },
  { code: "bg", name: "Bulgarian" },
  { code: "ca", name: "Catalan" },
  { code: "hr", name: "Croatian" },
  { code: "da", name: "Danish" },
  { code: "fi", name: "Finnish" },
  { code: "sk", name: "Slovak" },
  { code: "no", name: "Norwegian" },
  { code: "sq", name: "Albanian" },
  { code: "lt", name: "Lithuanian" },
  { code: "sl", name: "Slovenian" },
  { code: "lv", name: "Latvian" },
  { code: "et", name: "Estonian" },
  { code: "be", name: "Belarusian" },
  { code: "bs", name: "Bosnian" },
  { code: "mk", name: "Macedonian" },
  { code: "mt", name: "Maltese" },
  { code: "ga", name: "Irish" },
  { code: "cy", name: "Welsh" },
  { code: "is", name: "Icelandic" },
  { code: "ka", name: "Georgian" },
  { code: "hy", name: "Armenian" },
  { code: "he", name: "Hebrew" },
  { code: "eu", name: "Basque" },
  { code: "gl", name: "Galician" },
  { code: "lb", name: "Luxembourgish" },
];

export const SUPPORTED_LANGUAGE_CODES = new Set(
  SUPPORTED_LANGUAGES.map((lang) => lang.code)
);

export const MAX_LANGUAGES = 10;

export function getLanguageName(code: string): string | undefined {
  return SUPPORTED_LANGUAGES.find((lang) => lang.code === code)?.name;
}
