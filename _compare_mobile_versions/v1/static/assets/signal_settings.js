(function () {
  const STORAGE_KEY = "00919_signal_settings";
  const DEFAULTS = {
    premiumDiscountYellowPct: 1,
    premiumDiscountRedPct: 2,
    monthlyReturnRedPct: 0,
    beneficiaryDeclineMonths: 3,
    single54cThreshold: 20000,
    supplementalPremiumRatePct: 2.11,
    supplementalPremiumWarningAmount: 0,
    top10RotationWarningCount: 1,
    top10ConcentrationYellowPct: 75,
  };

  function toNumber(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function normalizeSettings(settings) {
    const premiumDiscountYellowPct = clamp(Math.abs(toNumber(settings.premiumDiscountYellowPct, DEFAULTS.premiumDiscountYellowPct)), 1, 10);
    const premiumDiscountRedPct = clamp(Math.abs(toNumber(settings.premiumDiscountRedPct, DEFAULTS.premiumDiscountRedPct)), 2, 10);
    return {
      premiumDiscountYellowPct,
      premiumDiscountRedPct: Math.max(premiumDiscountRedPct, premiumDiscountYellowPct),
      monthlyReturnRedPct: clamp(toNumber(settings.monthlyReturnRedPct, DEFAULTS.monthlyReturnRedPct), -100, 100),
      beneficiaryDeclineMonths: clamp(Math.round(toNumber(settings.beneficiaryDeclineMonths, DEFAULTS.beneficiaryDeclineMonths)), 1, 12),
      single54cThreshold: Math.max(0, toNumber(settings.single54cThreshold, DEFAULTS.single54cThreshold)),
      supplementalPremiumRatePct: clamp(toNumber(settings.supplementalPremiumRatePct, DEFAULTS.supplementalPremiumRatePct), 0, 10),
      supplementalPremiumWarningAmount: Math.max(0, toNumber(settings.supplementalPremiumWarningAmount, DEFAULTS.supplementalPremiumWarningAmount)),
      top10RotationWarningCount: clamp(Math.round(toNumber(settings.top10RotationWarningCount, DEFAULTS.top10RotationWarningCount)), 0, 10),
      top10ConcentrationYellowPct: clamp(toNumber(settings.top10ConcentrationYellowPct, DEFAULTS.top10ConcentrationYellowPct), 0, 100),
    };
  }

  function getSignalSettings() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return normalizeSettings({ ...DEFAULTS, ...stored });
    } catch {
      return { ...DEFAULTS };
    }
  }

  function saveSignalSettings(settings) {
    const normalized = normalizeSettings(settings);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    return normalized;
  }

  function resetSignalSettings() {
    localStorage.removeItem(STORAGE_KEY);
    return { ...DEFAULTS };
  }

  function fillSignalSettingsForm(settings = getSignalSettings()) {
    Object.entries({
      settingPremiumDiscountYellowPct: settings.premiumDiscountYellowPct,
      settingPremiumDiscountRedPct: settings.premiumDiscountRedPct,
      settingMonthlyReturnRedPct: settings.monthlyReturnRedPct,
      settingBeneficiaryDeclineMonths: settings.beneficiaryDeclineMonths,
      settingSingle54cThreshold: settings.single54cThreshold,
      settingSupplementalPremiumRatePct: settings.supplementalPremiumRatePct,
      settingSupplementalPremiumWarningAmount: settings.supplementalPremiumWarningAmount,
      settingTop10RotationWarningCount: settings.top10RotationWarningCount,
      settingTop10ConcentrationYellowPct: settings.top10ConcentrationYellowPct,
    }).forEach(([id, value]) => {
      const input = document.getElementById(id);
      if (input) input.value = value;
    });
  }

  function readSignalSettingsForm() {
    const value = (id) => document.getElementById(id)?.value;
    return normalizeSettings({
      premiumDiscountYellowPct: value("settingPremiumDiscountYellowPct"),
      premiumDiscountRedPct: value("settingPremiumDiscountRedPct"),
      monthlyReturnRedPct: value("settingMonthlyReturnRedPct"),
      beneficiaryDeclineMonths: value("settingBeneficiaryDeclineMonths"),
      single54cThreshold: value("settingSingle54cThreshold"),
      supplementalPremiumRatePct: value("settingSupplementalPremiumRatePct"),
      supplementalPremiumWarningAmount: value("settingSupplementalPremiumWarningAmount"),
      top10RotationWarningCount: value("settingTop10RotationWarningCount"),
      top10ConcentrationYellowPct: value("settingTop10ConcentrationYellowPct"),
    });
  }

  function rerenderDashboard() {
    if (typeof render === "function") render();
  }

  function showSettingsMessage(text) {
    const node = document.getElementById("signalSettingsMessage");
    if (!node) return;
    node.textContent = text;
    node.classList.add("show");
    window.clearTimeout(showSettingsMessage.timer);
    showSettingsMessage.timer = window.setTimeout(() => node.classList.remove("show"), 2200);
  }

  function bindSignalSettingsForm() {
    const form = document.getElementById("signalSettingsForm");
    if (!form) return;
    fillSignalSettingsForm();
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      saveSignalSettings(readSignalSettingsForm());
      fillSignalSettingsForm();
      rerenderDashboard();
      showSettingsMessage("燈號設定已儲存，頁面已依新門檻重新計算。");
    });
    document.getElementById("resetSignalSettingsButton")?.addEventListener("click", () => {
      fillSignalSettingsForm(resetSignalSettings());
      rerenderDashboard();
      showSettingsMessage("已恢復預設門檻。");
    });
  }

  window.SIGNAL_SETTINGS_DEFAULTS = DEFAULTS;
  window.getSignalSettings = getSignalSettings;
  window.saveSignalSettings = saveSignalSettings;
  window.resetSignalSettings = resetSignalSettings;
  window.bindSignalSettingsForm = bindSignalSettingsForm;

  document.addEventListener("DOMContentLoaded", bindSignalSettingsForm);
})();
