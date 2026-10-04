(() => {
  "use strict";

  if (new URLSearchParams(window.location.search).has("stay")) return;

  const exact = new Set([
    "ar-SA", "bn-BD", "ca", "zh-Hans", "zh-Hant", "hr", "cs", "da",
    "nl-NL", "en-AU", "en-CA", "en-GB", "en-US", "fi", "fr-CA",
    "fr-FR", "de-DE", "el", "gu-IN", "he", "hi", "hu", "id", "it",
    "ja", "kn-IN", "ko", "ms", "ml-IN", "mr-IN", "no", "or-IN", "pl",
    "pt-BR", "pt-PT", "pa-IN", "ro", "ru", "sk", "sl-SI", "es-MX",
    "es-ES", "sv", "ta-IN", "te-IN", "th", "tr", "uk", "ur-PK", "vi"
  ]);
  const fallback = {
    ar: "ar-SA", bn: "bn-BD", ca: "ca", zh: "zh-Hans", hr: "hr",
    cs: "cs", da: "da", nl: "nl-NL", en: "en-US", fi: "fi",
    fr: "fr-FR", de: "de-DE", el: "el", gu: "gu-IN", he: "he",
    iw: "he", hi: "hi", hu: "hu", id: "id", in: "id", it: "it",
    ja: "ja", kn: "kn-IN", ko: "ko", ms: "ms", ml: "ml-IN",
    mr: "mr-IN", no: "no", nb: "no", nn: "no", or: "or-IN",
    pl: "pl", pt: "pt-PT", pa: "pa-IN", ro: "ro", ru: "ru",
    sk: "sk", sl: "sl-SI", es: "es-ES", sv: "sv", ta: "ta-IN",
    te: "te-IN", th: "th", tr: "tr", uk: "uk", ur: "ur-PK", vi: "vi"
  };

  function match(tag) {
    const normalized = String(tag || "").replace("_", "-");
    const parts = normalized.split("-");
    const language = parts[0].toLowerCase();
    const region = (parts[1] || "").toUpperCase();
    if (language === "zh") {
      if (["TW", "HK", "MO"].includes(region) || /Hant/i.test(normalized)) {
        return "zh-Hant";
      }
      return "zh-Hans";
    }
    if (language === "en" && ["AU", "CA", "GB", "US"].includes(region)) {
      return `en-${region}`;
    }
    if (language === "fr" && region === "CA") return "fr-CA";
    if (language === "pt" && region === "BR") return "pt-BR";
    if (language === "es" && region === "MX") return "es-MX";
    return exact.has(normalized) ? normalized : fallback[language] || null;
  }

  const requested = navigator.languages && navigator.languages.length
    ? navigator.languages
    : [navigator.language];
  const target = requested.map(match).find(Boolean);
  if (target) window.location.replace(new URL(`${target}/index.html`, window.location.href).href);
})();
