// static/lang-switch.js
// Minimal client-side translation switcher.
// - Uses data-i18n attributes in templates.
// - Persists language by calling GET /set_language/<lang> (best-effort).
// - DOES NOT change server logic.

(function(){
  const TRANSLATIONS = {
    en: {
      advice_label: "Advice",
      symptoms_h4: "Symptoms",
      actions_h4: "Immediate actions",
      prevent_h4: "Prevention",
      treatment_h4: "Treatment / Notes",
      no_advice: "No advice available for this prediction.",
      feedback_title: "Feedback",
      feedback_hint: "Type feedback here...",
      feedback_send: "Send Feedback",
      quick_upload: "Upload another image",
      quick_history: "View my history",
      predicted_label: "Predicted:",
      confidence_prefix: "Confidence:",
      status_healthy: "Healthy",
      status_diseased: "Diseased — Action Needed",
      status_unknown: "Status Unknown",
      back_dashboard: "← Back to dashboard",
      logout: "Logout"
    },
    hi: {
      advice_label: "सलाह",
      symptoms_h4: "लक्षण",
      actions_h4: "तत्काल कार्रवाई",
      prevent_h4: "रोकथाम",
      treatment_h4: "उपचार / नोट्स",
      no_advice: "इस पूर्वानुमान के लिए कोई सलाह उपलब्ध नहीं है।",
      feedback_title: "प्रतिपुष्टि",
      feedback_hint: "यहाँ प्रतिक्रिया लिखें...",
      feedback_send: "प्रतिक्रिया भेजें",
      quick_upload: "एक और छवि अपलोड करें",
      quick_history: "मेरा इतिहास देखें",
      predicted_label: "पूर्वानुमान:",
      confidence_prefix: "विश्वास:",
      status_healthy: "स्वस्थ",
      status_diseased: "रोगग्रस्त — कार्रवाई आवश्यक",
      status_unknown: "स्थिति अज्ञात",
      back_dashboard: "← डैशबोर्ड पर वापस जाएँ",
      logout: "लॉग आउट"
    },
    mr: {
      advice_label: "सल्ला",
      symptoms_h4: "लक्षणे",
      actions_h4: "तत्काळ कृती",
      prevent_h4: "प्रतिबंधक उपाय",
      treatment_h4: "उपचार / टीप",
      no_advice: "या भाकीतासाठी सल्ला उपलब्ध नाही.",
      feedback_title: "अभिप्राय",
      feedback_hint: "येथे अभिप्राय टाका...",
      feedback_send: "अभिप्राय पाठवा",
      quick_upload: "एक इतर प्रतिमा अपलोड करा",
      quick_history: "माझे इतिहास पाहा",
      predicted_label: "भाकीत:",
      confidence_prefix: "विश्वास:",
      status_healthy: "सजग (Healthy)",
      status_diseased: "रोगग्रस्त — कृती आवश्यक",
      status_unknown: "स्थिती अज्ञात",
      back_dashboard: "← डॅशबोर्डवर परत जा",
      logout: "लॉग आउट"
    }
  };

  function apply(lang) {
    const map = TRANSLATIONS[lang] || TRANSLATIONS['en'];
    document.querySelectorAll('[data-i18n]').forEach(node => {
      const key = node.getAttribute('data-i18n');
      if (!key) return;
      const val = map[key];
      if (val === undefined) return;
      // If HTML allowed (small tags), use innerHTML for brand/back etc.
      if (/<[^>]+>/.test(val) && (node.tagName.toLowerCase() === 'a' || node.tagName.toLowerCase() === 'div' || node.tagName.toLowerCase() === 'span')) {
        node.innerHTML = val;
      } else {
        node.textContent = val;
      }
    });
  }

  function setActiveLangUI(lang) {
    document.querySelectorAll('.lang-select a').forEach(a => {
      const d = a.getAttribute('data-lang') || a.dataset.lang || (a.getAttribute('href')||'').split('/').pop();
      if (d === lang) a.classList.add('active'); else a.classList.remove('active');
    });
  }

  function persist(lang) {
    // best effort: update session on server so other pages render in that lang
    fetch('/set_language/' + encodeURIComponent(lang), { method: 'GET', credentials: 'same-origin' }).catch(()=>{});
  }

  function onNavClick(e) {
    e.preventDefault();
    const a = e.currentTarget;
    const chosen = a.getAttribute('data-lang') || a.dataset.lang || (a.getAttribute('href')||'').split('/').pop();
    if (!chosen) return;
    apply(chosen);
    setActiveLangUI(chosen);
    persist(chosen);
  }

  function init() {
    document.querySelectorAll('.lang-select a').forEach(a => a.addEventListener('click', onNavClick));

    // initial language: prefer server value if provided via window.__SERVER_LANG__
    const initial = (window.__SERVER_LANG__ || 'en');
    apply(initial);
    setActiveLangUI(initial);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  // expose for debugging
  window.__applyLang = apply;
})();
