const state = {
  data: null,
  trades: [],
  tradeAction: "buy",
  editingTradeId: "",
};

const HEALTH_PREMIUM_THRESHOLD = 20000;
const HEALTH_PREMIUM_RATE = 0.0211;

const fmt = {
  money(value, digits = 0) {
    if (!Number.isFinite(value)) return "--";
    return value.toLocaleString("zh-TW", {
      maximumFractionDigits: digits,
      minimumFractionDigits: digits,
    });
  },
  pct(value) {
    if (!Number.isFinite(value)) return "--";
    return `${value.toFixed(2)}%`;
  },
  lots(value) {
    if (!Number.isFinite(value)) return "--";
    return `${Math.round(value).toLocaleString("zh-TW")} 張`;
  },
};

function $(id) {
  return document.getElementById(id);
}

const ICONS = {
  activity: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 12h-4l-3 8-6-16-3 8H2"/></svg>`,
  barChart: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3v18h18"/><path d="M7 16v-5"/><path d="M12 16V7"/><path d="M17 16v-3"/></svg>`,
  briefcase: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 6V5a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1"/><rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 12h18"/><path d="M10 12v2h4v-2"/></svg>`,
  building: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18"/><path d="M6 12H4a2 2 0 0 0-2 2v8"/><path d="M18 9h2a2 2 0 0 1 2 2v11"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></svg>`,
  calculator: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M8 6h8"/><path d="M8 10h.01"/><path d="M12 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/><path d="M16 18h.01"/></svg>`,
  calendarDays: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 2v4"/><path d="M16 2v4"/><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/></svg>`,
  circleDollar: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 6v12"/><path d="M15 9.5c-.7-.8-1.7-1.2-3-1.2-1.7 0-3 .8-3 2.2 0 3.1 6 1.5 6 4.5 0 1.4-1.3 2.2-3 2.2-1.4 0-2.5-.4-3.3-1.3"/></svg>`,
  coins: `<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="8" cy="6" rx="5" ry="3"/><path d="M3 6v5c0 1.7 2.2 3 5 3s5-1.3 5-3V6"/><path d="M3 11v5c0 1.7 2.2 3 5 3 1.6 0 3-.4 3.9-1.1"/><path d="M16 10c2.8 0 5 1.3 5 3s-2.2 3-5 3-5-1.3-5-3 2.2-3 5-3Z"/><path d="M11 13v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4"/></svg>`,
  cpu: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2"/><path d="M9 1v4"/><path d="M15 1v4"/><path d="M9 19v4"/><path d="M15 19v4"/><path d="M1 9h4"/><path d="M1 15h4"/><path d="M19 9h4"/><path d="M19 15h4"/></svg>`,
  database: `<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg>`,
  home: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/></svg>`,
  layers: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></svg>`,
  lineChart: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-7"/></svg>`,
  pieChart: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v9h9"/><path d="M20.5 15A9 9 0 1 1 9 3.5"/><path d="M12 3a9 9 0 0 1 9 9"/></svg>`,
  star: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/></svg>`,
  trendingUp: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 17 6-6 4 4 8-8"/><path d="M14 7h7v7"/></svg>`,
  trafficCone: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l5 17H4L9 3Z"/><path d="M8 10h8"/><path d="M6.5 15h11"/><path d="M3 20h18"/></svg>`,
  user: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>`,
  users: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"/><circle cx="9.5" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/></svg>`,
  wallet: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1V8a1 1 0 0 0-1-1Z"/><path d="M16 12h.01"/><path d="M3 7h17"/></svg>`,
};

function renderIcon(name, colorClass = "green") {
  const icon = ICONS[name] || "";
  return `<span class="icon-box icon-box--${colorClass}">${icon}</span>`;
}

function hydrateInlineIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((node) => {
    const iconName = node.dataset.icon;
    const colorClass = node.dataset.iconColor || "green";
    node.outerHTML = renderIcon(iconName, colorClass);
  });
}

function prependDesktopIcon(selector, iconName, colorClass = "green") {
  const node = document.querySelector(selector);
  if (!node || node.querySelector(":scope > .icon-box")) return;
  node.classList.add("desktop-icon-target");
  node.insertAdjacentHTML("afterbegin", renderIcon(iconName, colorClass));
}

function hydrateDesktopIcons() {
  const iconTargets = [
    [".position-panel .panel-title > span", "briefcase", "green"],
    [".status-panel .panel-title > span", "activity", "green"],
    [".data-freshness-section .section-head h3", "database", "blue"],
    [".home-focus-section .section-head h3", "star", "green"],
    [".chart-section .section-head h3", "barChart", "cyan"],
    [".trade-section .section-head h3", "briefcase", "blue"],
    [".monthly-section .section-head h3", "trendingUp", "green"],
    [".quarterly-section .section-head h3", "coins", "orange"],
    [".holdings-section .section-head h3", "pieChart", "purple"],
    [".yearly-section .section-head h3", "calculator", "pink"],
    [".settings-section .section-head h3", "activity", "blue"],
  ];
  iconTargets.forEach(([selector, iconName, colorClass]) => prependDesktopIcon(selector, iconName, colorClass));

  [
    ["marketValue", "trendingUp", "green"],
    ["totalCost", "wallet", "blue"],
    ["unrealizedPnl", "pieChart", "orange"],
    ["annualDividend", "coins", "orange"],
    ["cumulativeDividend", "calculator", "purple"],
    ["totalReturn", "lineChart", "pink"],
    ["homeTotalReturn", "trendingUp", "green"],
    ["homeLatestDividend", "coins", "orange"],
    ["homeLatest54c", "circleDollar", "blue"],
    ["homePremiumWatch", "activity", "orange"],
    ["homeAum", "building", "purple"],
    ["homeBeneficiaries", "users", "blue"],
    ["homeTop10Total", "pieChart", "cyan"],
    ["homeTopHolding", "cpu", "pink"],
    ["freshDailyStatus", "barChart", "green"],
    ["freshMonthlyStatus", "building", "blue"],
    ["freshDividendStatus", "coins", "orange"],
    ["freshHoldingsStatus", "pieChart", "purple"],
    ["freshFetchedStatus", "database", "cyan"],
    ["freshIntegrityStatus", "activity", "pink"],
  ].forEach(([valueId, iconName, colorClass]) => {
    const card = $(valueId)?.closest(".metric, .focus-card, .freshness-card");
    if (!card || card.querySelector(":scope > .icon-box")) return;
    card.insertAdjacentHTML("afterbegin", renderIcon(iconName, colorClass));
  });
}

function signalText(level) {
  return {
    green: "綠燈",
    yellow: "黃燈",
    red: "紅燈",
    unknown: "待確認",
  }[level || "unknown"];
}

function getAppSignalSettings() {
  if (typeof window.getSignalSettings === "function") return window.getSignalSettings();
  return window.SIGNAL_SETTINGS_DEFAULTS || {
    premiumDiscountYellowPct: 1,
    premiumDiscountRedPct: 2,
  };
}

function calcDailySignal(latest) {
  const settings = getAppSignalSettings();
  const discountPct = Number(latest.premium_discount_pct);
  const volumeLots = Number(latest.volume_lots);
  const yellow = Math.abs(Number(settings.premiumDiscountYellowPct ?? 1));
  const red = Math.abs(Number(settings.premiumDiscountRedPct ?? 2));
  if (!Number.isFinite(discountPct)) {
    return { level: "unknown", reason: "尚未取得折溢價資料，暫時無法判斷每日燈號。" };
  }
  const absDiscount = Math.abs(discountPct);
  if (absDiscount >= red) {
    return {
      level: "red",
      reason: `折溢價 ${fmt.pct(discountPct)} 已超過紅燈門檻 ${fmt.pct(red)}，需要特別留意。`,
    };
  }
  if (absDiscount >= yellow) {
    return {
      level: "yellow",
      reason: `折溢價 ${fmt.pct(discountPct)} 已超過黃燈門檻 ${fmt.pct(yellow)}，先觀察是否只是短期偏離。`,
    };
  }
  if (!Number.isFinite(volumeLots) || volumeLots <= 0) {
    return { level: "yellow", reason: "折溢價正常，但成交量資料尚未完整，先列入觀察。" };
  }
  return {
    level: "green",
    reason: `折溢價 ${fmt.pct(discountPct)} 在設定門檻內，成交量資料正常。`,
  };
}

function signalSeverity(level) {
  return { red: 3, yellow: 2, unknown: 1, green: 0 }[level || "unknown"] ?? 1;
}

function calcHoldingSignalForSummary() {
  const settings = getAppSignalSettings();
  const holdings = state.data?.holdings || {};
  const history = state.data?.holdings_history || [];
  const top10 = holdings.top10 || [];
  if (!top10.length) {
    return {
      level: "unknown",
      reason: "持股：尚未取得前十大資料，請到持股頁確認資料來源。",
    };
  }
  const top10Total = top10.reduce((sum, row) => sum + Number(row.weight_pct || 0), 0);
  const concentrationThreshold = Number(settings.top10ConcentrationYellowPct ?? 75);
  if (top10Total >= concentrationThreshold) {
    return {
      level: "yellow",
      reason: `持股：前十大集中度 ${fmt.pct(top10Total)} 達到門檻，請到持股頁查看持股占比。`,
    };
  }
  const previous = [...history]
    .filter((row) => row.data_date && row.data_date !== holdings.data_date)
    .sort((a, b) => String(a.data_date).localeCompare(String(b.data_date)))
    .at(-1);
  if (previous) {
    const currentCodes = new Set(top10.map((row) => row.code).filter(Boolean));
    const previousCodes = new Set((previous.top10 || []).map((row) => row.code).filter(Boolean));
    const addedCount = [...currentCodes].filter((code) => !previousCodes.has(code)).length;
    const removedCount = [...previousCodes].filter((code) => !currentCodes.has(code)).length;
    const rotationCount = addedCount + removedCount;
    const rotationThreshold = Number(settings.top10RotationWarningCount ?? 1);
    if (rotationThreshold > 0 && rotationCount >= rotationThreshold) {
      return {
        level: "yellow",
        reason: `持股：前十大汰換 ${rotationCount} 檔，請到持股頁查看新增與淘汰紀錄。`,
      };
    }
  }
  return { level: "green", reason: "所有數據正常" };
}

function isFiniteValue(value) {
  if (value === null || value === undefined || value === "") return false;
  return Number.isFinite(Number(value));
}

function asNumber(value) {
  return isFiniteValue(value) ? Number(value) : NaN;
}

function getLatestMarketRow(rows = state.data?.daily || []) {
  return [...rows].reverse().find((row) => isFiniteValue(row.market_price)) || {};
}

function daysBetweenDates(startDate, endDate) {
  if (!startDate || !endDate) return NaN;
  const start = new Date(`${startDate}T00:00:00Z`);
  const end = new Date(`${endDate}T00:00:00Z`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return NaN;
  return Math.floor((end.getTime() - start.getTime()) / 86400000);
}

function collectDataIntegrityWarnings(latest = {}, dividend = {}, latestMonthly = {}, holdings = {}) {
  const warnings = [];
  const add = (level, label, impact) => warnings.push({ level, label, impact });
  const dailyRows = state.data?.daily || [];
  const dividendRows = state.data?.dividends || [];
  const monthlyRows = state.data?.monthly_history || state.data?.monthly_size || [];
  const top10Rows = holdings.top10 || [];

  if (!dailyRows.length) add("red", "日價格歷史", "折溢價圖表、月報酬與首頁市值都無法可靠計算");
  if (!latest.date) add("red", "最新交易日", "無法判斷每日價格是否過期");
  if (!isFiniteValue(latest.market_price)) add("red", "市價", "目前市值、未實現損益、含息報酬會失真");
  if (!isFiniteValue(latest.nav)) add("yellow", "淨值", "折溢價與淨值線會失真");
  if (!isFiniteValue(latest.premium_discount_pct)) add("yellow", "折溢價", "每日燈號與折溢價警示會失真");
  if (!isFiniteValue(latest.volume_lots)) add("yellow", "成交量", "成交量觀察會缺資料");

  const latestMarket = getLatestMarketRow(dailyRows);
  const navLagDays = daysBetweenDates(latest.date, latestMarket.date);
  if (Number.isFinite(navLagDays) && navLagDays >= 2) {
    add(
      "yellow",
      "淨值/折溢價更新落後",
      `市價已到 ${latestMarket.date}，但淨值與折溢價只到 ${latest.date}，已落後 ${navLagDays} 天，折溢價圖會停在完整資料日`
    );
  }

  if (!monthlyRows.length) add("yellow", "每月規模歷史", "AUM、受益人數與月度健康檢查無法判斷趨勢");
  if (!latestMonthly.month) add("yellow", "最新月資料", "無法判斷月規模資料是否過期");
  if (latestMonthly.month && !isFiniteValue(latestMonthly.aum_100m_twd ?? latestMonthly.aum_million_twd)) {
    add("yellow", "AUM", "ETF 規模健康會失真");
  }
  if (latestMonthly.month && !isFiniteValue(latestMonthly.beneficiary_count)) {
    add("yellow", "受益人數", "受益人數趨勢與月度燈號會失真");
  }

  if (!dividendRows.length) add("yellow", "配息歷史", "每季配息、年度配息與 54C 統計會缺資料");
  if (!dividend.ex_date) add("yellow", "最新除息日", "無法判斷配息資料是否過期");
  if (dividend.ex_date && !isFiniteValue(dividend.dividend_per_share)) add("yellow", "每股配息", "本次配息估算與年度配息會失真");
  if (dividend.ex_date && !isFiniteValue(dividend.estimated_54c_per_share)) add("yellow", "54C 組成", "54C 與補充保費估算會失真");

  if (!holdings.data_date) add("yellow", "持股資料日", "無法判斷前十大持股資料是否過期");
  if (!top10Rows.length) add("yellow", "前十大持股", "集中度、第一大持股與汰換紀錄會缺資料");

  return warnings;
}

function calcDataIntegrityStatus(latest, dividend, latestMonthly, holdings) {
  const warnings = collectDataIntegrityWarnings(latest, dividend, latestMonthly, holdings);
  if (!warnings.length) {
    return {
      status: { label: "正常", className: "green", note: "關鍵欄位完整" },
      warnings,
    };
  }
  const hasRed = warnings.some((warning) => warning.level === "red");
  const firstItems = warnings.slice(0, 2).map((warning) => warning.label).join("、");
  return {
    status: {
      label: hasRed ? "嚴重缺漏" : "需檢查",
      className: hasRed ? "red" : "yellow",
      note: `${warnings.length} 項：${firstItems}`,
    },
    warnings,
  };
}

function calcDataIntegritySignalForSummary(latest) {
  const monthlyRows = (state.data?.monthly_history || state.data?.monthly_size || [])
    .filter((row) => row.month && (row.aum_million_twd != null || row.aum_100m_twd != null || row.beneficiary_count != null))
    .sort((a, b) => String(a.month).localeCompare(String(b.month)));
  const latestMonthly = monthlyRows[monthlyRows.length - 1] || {};
  const dividend = state.data?.latest_dividend || {};
  const holdings = state.data?.holdings || {};
  const integrity = calcDataIntegrityStatus(latest, dividend, latestMonthly, holdings);
  if (!integrity.warnings.length) return { level: "green", reason: "資料完整性正常" };
  const level = integrity.warnings.some((warning) => warning.level === "red") ? "red" : "yellow";
  const firstWarning = integrity.warnings[0];
  return {
    level,
    reason: `資料完整性：缺少 ${firstWarning.label}，${firstWarning.impact}，請看首頁資料更新狀態。`,
  };
}

function calcDashboardSignal(latest) {
  const checks = [
    {
      ...calcDailySignal(latest),
      summaryReason: (signal) => `每日總覽：${signal.reason}，請看每日圖表的折溢價與成交量。`,
    },
  ];

  checks.push({
    ...calcDataIntegritySignalForSummary(latest),
    summaryReason: (signal) => signal.reason,
  });

  if (typeof calcMonthlyReturnRows === "function" && typeof calcMonthlySignal === "function") {
    const monthlyRows = calcMonthlyReturnRows(
      state.data.monthly_history || [],
      state.data.daily || [],
      state.trades || [],
      state.data.dividends || []
    );
    checks.push({
      ...calcMonthlySignal(monthlyRows),
      summaryReason: (signal) => `每月：${signal.reason} 請到每月頁查看含息報酬與 ETF 規模健康。`,
    });
  }

  if (typeof calcYearlyTaxRows === "function" && typeof calcYearlyTaxSignal === "function") {
    const yearlyRows = calcYearlyTaxRows(state.data.dividends || [], state.trades || []);
    checks.push({
      ...calcYearlyTaxSignal(yearlyRows),
      summaryReason: (signal) => `每年：${signal.reason} 請到每年頁查看 54C 與補充保費。`,
    });
  }

  const holdingSignal = calcHoldingSignalForSummary();
  checks.push({
    ...holdingSignal,
    summaryReason: (signal) => signal.reason,
  });

  const abnormal = checks
    .filter((item) => signalSeverity(item.level) > 0)
    .sort((a, b) => signalSeverity(b.level) - signalSeverity(a.level));

  if (!abnormal.length) {
    return { level: "green", reason: "所有數據正常" };
  }

  const level = abnormal.some((item) => item.level === "red") ? "red" : "yellow";
  const reason = abnormal
    .slice(0, 3)
    .map((item) => (typeof item.summaryReason === "function" ? item.summaryReason(item) : item.reason))
    .join("；");
  return { level, reason };
}

function setText(id, value) {
  const node = $(id);
  if (node) node.textContent = value;
}

async function loadData() {
  const [dashboardResponse, tradesResponse] = await Promise.all([
    fetch(`data/dashboard_data.json?ts=${Date.now()}`),
    fetch(`data/trades.json?ts=${Date.now()}`),
  ]);
  if (!dashboardResponse.ok) {
    throw new Error(`資料檔讀取失敗：HTTP ${dashboardResponse.status}`);
  }
  if (!tradesResponse.ok) {
    throw new Error(`交易紀錄讀取失敗：HTTP ${tradesResponse.status}`);
  }
  state.data = await dashboardResponse.json();
  const serverTrades = normalizeTrades(await tradesResponse.json());
  state.trades = serverTrades;
  if (window.__00919_TRADES_SOURCE?.message) {
    console.info(`[00919] ${window.__00919_TRADES_SOURCE.message}`);
  }
  saveTrades();
  render();
}

function normalizeTrades(trades) {
  return trades.map((trade, index) => ({
    id: trade.id || `trade-${trade.trade_date || "date"}-${index}-${trade.action || "buy"}`,
    action: trade.action || "buy",
    trade_date: normalizeTradeDate(trade.trade_date),
    shares: Number(trade.shares || 0),
    price: Number(trade.price || 0),
    fee: Number(trade.fee || 0),
    tax: Number(trade.tax || 0),
    note_type: trade.note_type || trade.note || "其他",
    note: trade.note || "",
  }));
}

function normalizeTradeDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;

  const separated = raw.match(/^(\d{4})[\/. -](\d{1,2})[\/. -](\d{1,2})$/);
  if (separated) {
    const [, year, month, day] = separated;
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }

  const compact = raw.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compact) {
    const [, year, month, day] = compact;
    return `${year}-${month}-${day}`;
  }

  return raw;
}

function bindInputs() {
  $("refreshButton").addEventListener("click", () => refreshDashboardData());
  $("homeRefreshButton")?.addEventListener("click", () => refreshDashboardData());
  $("mobileRefreshButton")?.addEventListener("click", () => refreshDashboardData());
  bindQuickModuleActions();
  $("rangeSelect").addEventListener("change", () => render());
  $("mobileRangeSelect")?.addEventListener("change", () => render());
  $("desktopRangeSelect")?.addEventListener("change", () => render());
  window.addEventListener("resize", debounce(() => {
    if (state.data) {
      drawChart(state.data.daily || [], $("rangeSelect").value);
      drawDesktopTrendChart(state.data.daily || [], $("desktopRangeSelect")?.value || "month");
      drawMobileChart(state.data.daily || [], $("mobileRangeSelect")?.value || "month");
      notifyDashboardRendered();
    }
  }, 150));
  bindTradeForm();
}

function bindQuickModuleActions() {
  document.querySelectorAll(".desktop-home .desktop-action-button[href^='#']").forEach((button) => {
    button.addEventListener("click", (event) => {
      const targetHash = button.getAttribute("href");
      const target = targetHash ? document.querySelector(targetHash) : null;
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      history.pushState(null, "", targetHash);
      document.querySelectorAll(".nav a[href^='#']").forEach((link) => {
        link.classList.toggle("active", link.getAttribute("href") === targetHash);
      });
    });
  });
}

function debounce(callback, wait) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), wait);
  };
}

function requestStreamlitUpdate() {
  if (!window.__00919_STREAMLIT_EMBED) return false;

  try {
    const parentUrl = new URL(window.parent.location.href);
    parentUrl.searchParams.set("run_update", "1");
    parentUrl.searchParams.set("update_ts", String(Date.now()));
    window.parent.location.href = parentUrl.toString();
    return true;
  } catch (error) {
    console.error(error);
    alert("請使用頁面左上角綠底的更新資料按鈕，讓 Streamlit 執行完整資料更新。");
    return true;
  }
}

function encodeBase64Url(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function requestStreamlitTradeSync(trades = state.trades, reason = "trade-edit") {
  if (!window.__00919_STREAMLIT_EMBED) return false;

  try {
    let baseHref = "";
    try {
      baseHref = window.parent.location.href;
    } catch (_) {
      baseHref = document.referrer || window.location.href;
    }
    const parentUrl = new URL(baseHref || window.location.href);
    const form = document.createElement("form");
    form.method = "GET";
    form.target = "_top";
    form.action = `${parentUrl.origin}${parentUrl.pathname}`;

    Object.entries({
      sync_trades: encodeBase64Url(JSON.stringify(trades || [])),
      sync_reason: reason,
      sync_ts: String(Date.now()),
    }).forEach(([name, value]) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();
    return true;
  } catch (error) {
    console.error(error);
    alert("交易紀錄已先儲存在這台裝置；瀏覽器擋下雲端同步，請先匯出資料備份。");
    return false;
  }
}

function requestStreamlitTradeAppend(trade) {
  if (!window.__00919_STREAMLIT_EMBED) return false;

  try {
    let baseHref = "";
    try {
      baseHref = window.parent.location.href;
    } catch (_) {
      baseHref = document.referrer || window.location.href;
    }
    const parentUrl = new URL(baseHref || window.location.href);
    parentUrl.search = "";
    const params = {
      append_trade: encodeBase64Url(JSON.stringify(trade || {})),
      append_ts: String(Date.now()),
    };
    Object.entries(params).forEach(([name, value]) => parentUrl.searchParams.set(name, value));
    console.info("[00919] append request 已送出", Object.keys(params));

    try {
      window.parent.location.href = parentUrl.toString();
      return true;
    } catch (_) {
      const link = document.createElement("a");
      link.href = parentUrl.toString();
      link.target = "_top";
      link.rel = "noreferrer";
      document.body.appendChild(link);
      link.click();
    }
    return true;
  } catch (error) {
    console.error(error);
    alert("寫入 Google Sheets 失敗：瀏覽器擋下雲端寫入請求。");
    return false;
  }
}

async function refreshDashboardData() {
  const buttons = [
    $("refreshButton"),
    $("homeRefreshButton"),
    $("mobileRefreshButton"),
  ].filter(Boolean);
  if (requestStreamlitUpdate()) {
    buttons.forEach((button) => {
      button.disabled = true;
      button.classList.add("is-loading");
      button.textContent = "更新中";
    });
    setText("freshFetchedStatus", "更新中");
    setText("freshFetchedAt", "正在交給 Streamlit 執行完整資料更新");
    return;
  }
  buttons.forEach((button) => {
    button.disabled = true;
    button.classList.add("is-loading");
  });
  const homeButton = $("homeRefreshButton");
  const originalText = homeButton?.textContent;
  if (homeButton) homeButton.textContent = "抓取中";
  setText("freshFetchedStatus", "抓取中");
  setText("freshFetchedAt", "正在更新價格、月規模、配息 54C 與前十大持股");

  let updateMode = "static";
  let updateAt = new Date().toLocaleString("zh-TW", { hour12: false });

  try {
    try {
      const updateResponse = await fetch(`/api/update?ts=${Date.now()}`, { method: "POST" });
      if (updateResponse.ok) {
        const updateResult = await updateResponse.json();
        updateMode = "api";
        updateAt = updateResult.updatedAt
          ? new Date(updateResult.updatedAt).toLocaleString("zh-TW", { hour12: false })
          : updateAt;
      } else if (![404, 405, 501].includes(updateResponse.status)) {
        let message = `HTTP ${updateResponse.status}`;
        try {
          const updateResult = await updateResponse.json();
          message = updateResult.error || updateResult.stderr || message;
        } catch (_) {
          // Keep the HTTP status message when the server does not return JSON.
        }
        throw new Error(`全資料更新失敗：${message}`);
      }
    } catch (apiError) {
      if (String(apiError.message || "").startsWith("全資料更新失敗")) throw apiError;
      updateMode = "static";
    }

    await loadData();
    setText("freshFetchedStatus", updateMode === "api" ? "已完成抓取" : "已重新讀取");
    setText(
      "freshFetchedAt",
      updateMode === "api"
        ? `${updateAt} / 全資料更新`
        : `${updateAt} / 靜態模式，已重新讀取現有資料檔`
    );
    if (homeButton) homeButton.textContent = "已完成";
    window.setTimeout(() => {
      if (homeButton) homeButton.textContent = originalText || "更新資料";
    }, 1200);
  } catch (error) {
    console.error(error);
    setText("freshFetchedStatus", "抓取失敗");
    setText("freshFetchedAt", error.message || "請確認資料檔與本機服務");
    if (homeButton) homeButton.textContent = "抓取失敗";
  } finally {
    buttons.forEach((button) => {
      button.disabled = false;
      button.classList.remove("is-loading");
    });
  }
}
function render() {
  if (!state.data) return;

  const latest = state.data.latest_daily || {};
  const latestMarket = getLatestMarketRow();
  const latestForPrice = latestMarket.date ? { ...latest, ...latestMarket } : latest;
  const dividend = state.data.latest_dividend || {};
  const signals = calcDashboardSignal(latest);
  const position = calcPosition(state.trades || [], state.data.dividends || []);
  const shares = position.holdingShares;
  const avgCost = position.avgCost;
  const marketPrice = asNumber(latestForPrice.market_price);
  const totalCost = position.totalCost;
  const marketValue = shares * marketPrice;
  const unrealizedPnl = marketValue - totalCost;
  const estimatedAnnualDividend = shares * Number(dividend.dividend_per_share || 0) * 4;
  const cumulativeDividend = position.cumulativeDividend;
  const totalReturn = unrealizedPnl + cumulativeDividend + position.realizedPnl;
  const estimated54c = shares * Number(dividend.estimated_54c_per_share || 0);
  const healthPremium = estimated54c >= HEALTH_PREMIUM_THRESHOLD ? estimated54c * HEALTH_PREMIUM_RATE : 0;

  setText("fetchedAt", `抓取時間 ${formatFetchedAt(state.data.fetched_at)}`);
  setText("latestDate", latestForPrice.date === latest.date ? latest.date || "--" : `市價 ${latestForPrice.date} / 淨值 ${latest.date || "--"}`);
  setText("holdingShares", `${fmt.money(shares)} 股`);
  setText("avgCost", fmt.money(avgCost, 2));
  setText("firstTradeDate", position.firstTradeDate || "--");
  setText("marketValue", `$${fmt.money(marketValue)}`);
  setText("totalCost", `$${fmt.money(totalCost)}`);
  setText("unrealizedPnl", `$${fmt.money(unrealizedPnl)}`);
  setText("annualDividend", `$${fmt.money(estimatedAnnualDividend)}`);
  setText("cumulativeDividend", `$${fmt.money(cumulativeDividend)}`);
  setText("totalReturn", `$${fmt.money(totalReturn)}`);
  $("unrealizedPnl").className = unrealizedPnl >= 0 ? "positive" : "negative";
  $("totalReturn").className = totalReturn >= 0 ? "positive" : "negative";

  const light = $("signalLight");
  light.className = `signal-light ${signals.level || "yellow"}`;
  setText("signalLabel", signalText(signals.level));
  setText("signalReason", signals.reason || "--");

  setText("latestPrice", fmt.money(asNumber(latestForPrice.market_price), 2));
  setText("latestNav", fmt.money(asNumber(latest.nav), 2));
  setText("latestDiscount", fmt.pct(asNumber(latest.premium_discount_pct)));
  setText("latestVolume", fmt.lots(asNumber(latestForPrice.volume_lots)));
  const freshnessModel = getFreshnessModel(latest, dividend, latestForPrice);
  renderDataFreshness(latest, dividend, freshnessModel);
  renderHomeFocus(position, latestForPrice, dividend, totalReturn, totalCost);
  const renderModel = {
    latest,
    latestForPrice,
    dividend,
    signals,
    position,
    shares,
    avgCost,
    marketValue,
    totalCost,
    unrealizedPnl,
    estimatedAnnualDividend,
    cumulativeDividend,
    totalReturn,
    totalReturnRate: totalCost ? (totalReturn / totalCost) * 100 : 0,
    estimated54c,
    healthPremium,
    freshnessModel,
  };
  renderDesktopHome(renderModel);
  renderMobileHome(renderModel);

  renderTradeTable(position, latestForPrice);
  renderQuarterlyDividends(state.data.dividends || [], state.trades || []);
  drawChart(state.data.daily || [], $("rangeSelect").value);
  drawDesktopTrendChart(state.data.daily || [], $("desktopRangeSelect")?.value || "month");
  drawMobileChart(state.data.daily || [], $("mobileRangeSelect")?.value || "month");
  notifyDashboardRendered();
}

function notifyDashboardRendered() {
  window.dispatchEvent(new Event("dashboard:rendered"));
}

function parseDateOnly(dateText) {
  if (!dateText) return null;
  const date = new Date(`${String(dateText).slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function daysSince(dateText) {
  const date = parseDateOnly(dateText);
  if (!date) return null;
  const today = new Date();
  const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.max(0, Math.floor((todayMidnight - date) / 86400000));
}

function businessDaysSince(dateText) {
  const date = parseDateOnly(dateText);
  if (!date) return null;
  const today = new Date();
  const cursor = new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1);
  const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  let days = 0;
  while (cursor <= todayMidnight) {
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) days += 1;
    cursor.setDate(cursor.getDate() + 1);
  }
  return Math.max(0, days);
}

function freshnessLabel(days, okDays, staleDays) {
  if (days === null) return { label: "待確認", className: "unknown", note: "尚無日期" };
  if (days <= okDays) return { label: "正常", className: "green", note: `${days} 天前` };
  if (days <= staleDays) return { label: "建議更新", className: "yellow", note: `${days} 天前` };
  return { label: "已過期", className: "red", note: `${days} 天前` };
}

function marketFreshnessLabel(dateText) {
  const tradingDays = businessDaysSince(dateText);
  const calendarDays = daysSince(dateText);
  if (tradingDays === null) return { label: "待確認", className: "unknown", note: "尚無日期" };
  const note = tradingDays <= 1
    ? "最近交易日"
    : `${tradingDays} 交易日前`;
  if (tradingDays <= 1) return { label: "正常", className: "green", note };
  if (tradingDays <= 3) return { label: "建議更新", className: "yellow", note };
  return { label: "已過期", className: "red", note: `${calendarDays} 天前` };
}

function formatFetchedAt(value) {
  if (!value) return "--";
  return String(value).replace("T", " ").slice(0, 19);
}

function setFreshness(idPrefix, status) {
  const statusNode = $(`${idPrefix}Status`);
  if (statusNode) {
    statusNode.textContent = status.label;
    statusNode.className = `freshness-status ${status.className}`;
  }
}

function getFreshnessModel(latestComplete, dividend, latestMarket = getLatestMarketRow()) {
  const latest = latestComplete || {};
  const monthlyRows = (state.data.monthly_history || state.data.monthly_size || [])
    .filter((row) => row.month && (row.aum_million_twd != null || row.aum_100m_twd != null || row.beneficiary_count != null))
    .sort((a, b) => String(a.month).localeCompare(String(b.month)));
  const latestMonthly = monthlyRows[monthlyRows.length - 1] || {};
  const holdings = state.data.holdings || {};
  const fetchedAt = String(state.data.fetched_at || "").slice(0, 10);

  const daily = marketFreshnessLabel(latestMarket.date || latest.date);
  const monthly = freshnessLabel(daysSince(latestMonthly.month ? `${latestMonthly.month}-28` : ""), 45, 75);
  const dividendStatus = freshnessLabel(daysSince(dividend.ex_date), 120, 180);
  const holdingsStatus = freshnessLabel(daysSince(holdings.data_date), 14, 30);
  const fetched = freshnessLabel(daysSince(fetchedAt), 2, 7);
  const integrity = calcDataIntegrityStatus(latest, dividend, latestMonthly, holdings);

  return {
    daily,
    monthly,
    dividend: dividendStatus,
    holdings: holdingsStatus,
    fetched,
    integrity,
    latestMonthly,
    holdingsData: holdings,
    latestMarket,
    fetchedAt,
    fetchedAtDisplay: formatFetchedAt(state.data.fetched_at),
  };
}

function renderDataFreshness(latest, dividend, model = getFreshnessModel(latest, dividend)) {
  setFreshness("freshDaily", model.daily);
  const marketDate = model.latestMarket?.date || latest.date;
  const navNote = model.latestMarket?.date && latest.date && model.latestMarket.date > latest.date
    ? `市價 ${model.latestMarket.date}；淨值 ${latest.date}`
    : model.daily.note;
  setText("freshDailyDate", marketDate ? `${marketDate} / ${navNote}` : "--");
  setFreshness("freshMonthly", model.monthly);
  setText("freshMonthlyDate", model.latestMonthly.month ? `${model.latestMonthly.month} / ${model.monthly.note}` : "--");
  setFreshness("freshDividend", model.dividend);
  setText("freshDividendDate", dividend.ex_date ? `${dividend.ex_date} / ${model.dividend.note}` : "--");
  setFreshness("freshHoldings", model.holdings);
  setText("freshHoldingsDate", model.holdingsData.data_date ? `${model.holdingsData.data_date} / ${model.holdings.note}` : "--");
  setFreshness("freshFetched", model.fetched);
  setText("freshFetchedAt", model.fetchedAt ? `${model.fetchedAtDisplay} / ${model.fetched.note}` : "--");
  setFreshness("freshIntegrity", model.integrity.status);
  setText("freshIntegrityNote", model.integrity.status.note);
}

function statusRank(status) {
  return { red: 3, yellow: 2, unknown: 1, green: 0 }[status?.className] ?? 1;
}

function pickWorstStatus(...statuses) {
  return statuses.filter(Boolean).sort((a, b) => statusRank(b) - statusRank(a))[0] || {
    label: "未知",
    className: "unknown",
    note: "尚無資料",
  };
}

function tradeStatus(position) {
  if (!position || position.holdingShares <= 0 || !position.firstTradeDate) {
    return { label: "未知", className: "unknown", note: "待輸入交易" };
  }
  return { label: "正常", className: "green", note: "已同步" };
}

function statusLine(status) {
  return `● ${status.label}　${status.note}`;
}

function formatStatusShort(status, count = 0) {
  const level = status?.className || status?.level || "unknown";
  if (level === "green") return "正常";
  if (level === "yellow") return count > 0 ? `需留意 ${count} 項` : "需留意";
  if (level === "red") return count > 0 ? `異常 ${count} 項` : "異常";
  return "待確認";
}

function setMobileMetric(id, valueId, statusId, value, status) {
  const tile = document.querySelector(`[data-mobile-metric="${id}"]`) || $(valueId)?.closest(".core-metric-tile");
  if (tile) tile.dataset.status = status.className || "unknown";
  setText(valueId, value);
  setText(statusId, statusLine(status));
}

function setDesktopMetric(id, valueId, statusId, value, status) {
  const tile = document.querySelector(`[data-desktop-metric="${id}"]`) || $(valueId)?.closest(".core-metric-tile");
  if (tile) tile.dataset.status = status.className || "unknown";
  setText(valueId, value);
  setText(statusId, "");
}

function buildMobileMetricStatusMap(freshnessModel, position) {
  const trade = tradeStatus(position);
  const dailyTrade = pickWorstStatus(freshnessModel.daily, trade);
  const dividendTrade = pickWorstStatus(freshnessModel.dividend, trade);
  return {
    shares: trade,
    avgCost: trade,
    firstTrade: trade,
    marketValue: dailyTrade,
    totalCost: trade,
    unrealizedPnl: dailyTrade,
    annualDividend: dividendTrade,
    totalReturn: pickWorstStatus(freshnessModel.daily, freshnessModel.dividend, trade),
    cumulativeDividend: dividendTrade,
  };
}

function renderMobileHero({ latest, signals, freshnessModel }) {
  const orb = $("mobileSignalOrb");
  const level = signals.level || "yellow";
  const firstWarning = freshnessModel.integrity?.warnings?.[0];
  const warningLabel = firstWarning ? firstWarning.label : "";
  if (orb) orb.className = `hero-status-orb ${level}`;
  setText("mobileSignalLabel", signalText(level));
  setText("mobileSignalReason", level === "green" ? "所有數據正常" : warningLabel || "請檢查資料");
  setText("mobileFetchedAt", `目前資料抓取時間 ${formatFetchedAt(state.data.fetched_at)}`);
  setText("mobileHeroPremium", `折溢價 ${fmt.pct(asNumber(latest.premium_discount_pct))}`);
  const chip = $("mobileFetchedAt");
  if (chip) chip.className = `ui-status-chip hero-time-chip ui-status-chip--${freshnessModel.fetched.className}`;
}

function renderMobileCoreMetrics(model) {
  const statuses = buildMobileMetricStatusMap(model.freshnessModel, model.position);
  setMobileMetric("shares", "mobileShares", "mobileSharesStatus", `${fmt.money(model.shares)} 股`, statuses.shares);
  setMobileMetric("avgCost", "mobileAvgCost", "mobileAvgCostStatus", fmt.money(model.avgCost, 2), statuses.avgCost);
  setMobileMetric("firstTrade", "mobileFirstTradeDate", "mobileFirstTradeStatus", model.position.firstTradeDate || "--", statuses.firstTrade);
  setMobileMetric("marketValue", "mobileMarketValue", "mobileMarketValueStatus", `$${fmt.money(model.marketValue)}`, statuses.marketValue);
  setMobileMetric("totalCost", "mobileTotalCost", "mobileTotalCostStatus", `$${fmt.money(model.totalCost)}`, statuses.totalCost);
  setMobileMetric("unrealizedPnl", "mobileUnrealizedPnl", "mobileUnrealizedPnlStatus", `$${fmt.money(model.unrealizedPnl)}`, statuses.unrealizedPnl);
  setMobileMetric("annualDividend", "mobileAnnualDividend", "mobileAnnualDividendStatus", `$${fmt.money(model.estimatedAnnualDividend)}`, statuses.annualDividend);
  setMobileMetric("totalReturn", "mobileTotalReturn", "mobileTotalReturnStatus", `$${fmt.money(model.totalReturn)}`, statuses.totalReturn);
  setMobileMetric("cumulativeDividend", "mobileCumulativeDividend", "mobileCumulativeDividendStatus", `$${fmt.money(model.cumulativeDividend)}`, statuses.cumulativeDividend);

  const statusList = Object.values(statuses);
  const greenCount = statusList.filter((status) => status.className === "green").length;
  const counter = $("mobileCoreUpdateCount");
  if (counter) {
    const integrityWarnings = model.freshnessModel.integrity?.warnings || [];
    const worst = pickWorstStatus(...statusList, model.freshnessModel.integrity?.status);
    counter.textContent = integrityWarnings.length
      ? `${integrityWarnings.length} 項需檢查`
      : `${greenCount}/9 ${greenCount === 9 ? "已更新" : "需檢查"}`;
    counter.className = `ui-status-chip ui-status-chip--${worst.className}`;
  }
}

function renderMobileFocusCards({ position, dividend, totalReturn, totalCost, freshnessModel }) {
  const totalReturnRate = totalCost ? (totalReturn / totalCost) * 100 : 0;
  setText("mobileFocusTotalReturn", `$${fmt.money(totalReturn)}`);
  setText("mobileFocusTotalReturnRate", fmt.pct(totalReturnRate));

  const dividendPerShare = Number(dividend.dividend_per_share || 0);
  const dividendShares = dividend.ex_date ? calcSharesOnDate(state.trades || [], dividend.ex_date) : position.holdingShares;
  const estimatedDividendCash = dividendShares * dividendPerShare;
  setText("mobileFocusDividend", dividendPerShare ? `${fmt.money(dividendPerShare, 2)} 元` : "--");
  setText("mobileFocusDividendNote", dividend.ex_date ? `除息 ${dividend.ex_date} / 估 $${fmt.money(estimatedDividendCash)}` : "--");

  const latestSize = freshnessModel.latestMonthly || {};
  const aumMillion = Number(latestSize.aum_million_twd || Number(latestSize.aum_100m_twd) * 100);
  setText("mobileFocusBeneficiaries", Number.isFinite(Number(latestSize.beneficiary_count)) ? `${fmt.money(Number(latestSize.beneficiary_count))} 人` : "--");
  setText("mobileFocusBeneficiariesNote", Number.isFinite(Number(latestSize.beneficiary_change_pct)) ? `月變化 ${fmt.pct(Number(latestSize.beneficiary_change_pct))}` : "--");
  setText("mobileFocusAum", Number.isFinite(aumMillion) ? `${fmt.money(aumMillion / 100)} 億` : "--");
  setText("mobileFocusAumNote", latestSize.month || "--");

  const holdings = freshnessModel.holdingsData || {};
  const top10 = holdings.top10 || [];
  const top10Total = top10.reduce((sum, row) => sum + Number(row.weight_pct || 0), 0);
  setText("mobileFocusTop10", top10.length ? fmt.pct(top10Total) : "--");
  setText("mobileFocusTop10Note", holdings.data_date ? `資料日 ${holdings.data_date}` : "--");
  setText("mobileFocusTopHolding", top10[0] ? `${top10[0].name} ${top10[0].code || ""}` : "--");
  setText("mobileFocusTopHoldingNote", top10[0] ? fmt.pct(Number(top10[0].weight_pct || 0)) : "--");
}

function renderMobileHome(model) {
  if (!$("mobileMainChart")) return;
  renderMobileHero(model);
  renderMobileCoreMetrics(model);
  renderMobileFocusCards(model);
}

function renderDesktopHome(model) {
  if (!$("desktopMainChart")) return;
  renderDesktopHero(model);
  renderDesktopCoreMetrics(model);
  renderDesktopFocusCards(model);
  renderDesktopModuleCards(model);
  renderDesktopDataStatusCompact(model.latest, model.dividend, model.freshnessModel);
}

function renderDesktopHero({ signals, freshnessModel, shares, totalReturn, totalReturnRate }) {
  const level = signals.level || "yellow";
  const orb = $("desktopSignalOrb");
  const sidebarDot = document.querySelector(".sidebar-signal__dot");
  const warningCount = freshnessModel.integrity?.warnings?.length || 0;
  const shortReason = level === "green" ? "所有數據正常" : formatStatusShort({ className: level }, warningCount || 1);
  if (orb) orb.className = `desktop-hero__orb ${level}`;
  if (sidebarDot) sidebarDot.dataset.status = level;
  setText("desktopSignalLabel", signalText(level));
  setText("desktopSignalReason", shortReason);
  setText("sidebarSignalLabel", signalText(level));
  setText("sidebarSignalReason", shortReason);
  setText("desktopFetchedAt", `資料更新時間 ${formatFetchedAt(state.data.fetched_at)}`);
  const chip = $("desktopFetchedAt");
  if (chip) chip.className = `ui-status-chip hero-time-chip ui-status-chip--${freshnessModel.fetched.className}`;

  const statuses = buildMobileMetricStatusMap(freshnessModel, { holdingShares: shares, firstTradeDate: true });
  setText("desktopHeroShares", `${fmt.money(shares)} 股`);
  setText("desktopHeroSharesStatus", statusLine(statuses.shares));
  setText("desktopHeroTotalReturn", `$${fmt.money(totalReturn)}`);
  setText("desktopHeroTotalReturnRate", fmt.pct(totalReturnRate));
  $("desktopHeroTotalReturn")?.classList.toggle("negative", totalReturn < 0);
  $("desktopHeroTotalReturn")?.classList.toggle("positive", totalReturn >= 0);
}

function renderDesktopCoreMetrics(model) {
  const statuses = buildMobileMetricStatusMap(model.freshnessModel, model.position);
  setDesktopMetric("shares", "desktopShares", "desktopSharesStatus", `${fmt.money(model.shares)} 股`, statuses.shares);
  setDesktopMetric("avgCost", "desktopAvgCost", "desktopAvgCostStatus", fmt.money(model.avgCost, 2), statuses.avgCost);
  setDesktopMetric("firstTrade", "desktopFirstTradeDate", "desktopFirstTradeStatus", model.position.firstTradeDate || "--", statuses.firstTrade);
  setDesktopMetric("marketValue", "desktopMarketValue", "desktopMarketValueStatus", `$${fmt.money(model.marketValue)}`, statuses.marketValue);
  setDesktopMetric("totalCost", "desktopTotalCost", "desktopTotalCostStatus", `$${fmt.money(model.totalCost)}`, statuses.totalCost);
  setDesktopMetric("unrealizedPnl", "desktopUnrealizedPnl", "desktopUnrealizedPnlStatus", `$${fmt.money(model.unrealizedPnl)}`, statuses.unrealizedPnl);
  setDesktopMetric("annualDividend", "desktopAnnualDividend", "desktopAnnualDividendStatus", `$${fmt.money(model.estimatedAnnualDividend)}`, statuses.annualDividend);
  setDesktopMetric("totalReturn", "desktopTotalReturn", "desktopTotalReturnStatus", `$${fmt.money(model.totalReturn)}`, statuses.totalReturn);
  setDesktopMetric("cumulativeDividend", "desktopCumulativeDividend", "desktopCumulativeDividendStatus", `$${fmt.money(model.cumulativeDividend)}`, statuses.cumulativeDividend);
  $("desktopUnrealizedPnl")?.classList.toggle("negative", model.unrealizedPnl < 0);
  $("desktopUnrealizedPnl")?.classList.toggle("positive", model.unrealizedPnl >= 0);
  $("desktopTotalReturn")?.classList.toggle("negative", model.totalReturn < 0);
  $("desktopTotalReturn")?.classList.toggle("positive", model.totalReturn >= 0);

  const statusList = Object.values(statuses);
  const greenCount = statusList.filter((status) => status.className === "green").length;
  const counter = $("desktopCoreUpdateCount");
  if (counter) {
    const worst = pickWorstStatus(...statusList);
    counter.textContent = `${greenCount}/9 ${greenCount === 9 ? "已更新" : "需檢查"}`;
    counter.className = `ui-status-chip ui-status-chip--${worst.className}`;
  }
}

function renderDesktopFocusCards({ position, dividend, totalReturn, totalCost, freshnessModel }) {
  const totalReturnRate = totalCost ? (totalReturn / totalCost) * 100 : 0;
  setText("desktopFocusTotalReturn", `$${fmt.money(totalReturn)}`);
  setText("desktopFocusTotalReturnRate", fmt.pct(totalReturnRate));

  const dividendPerShare = Number(dividend.dividend_per_share || 0);
  const dividendShares = dividend.ex_date ? calcSharesOnDate(state.trades || [], dividend.ex_date) : position.holdingShares;
  const estimatedDividendCash = dividendShares * dividendPerShare;
  setText("desktopFocusDividend", dividendPerShare ? `${fmt.money(dividendPerShare, 2)} 元` : "--");
  setText("desktopFocusDividendNote", dividend.ex_date ? `除息 ${dividend.ex_date} / 估 $${fmt.money(estimatedDividendCash)}` : "--");

  const latestSize = freshnessModel.latestMonthly || {};
  const aumMillion = Number(latestSize.aum_million_twd || Number(latestSize.aum_100m_twd) * 100);
  setText("desktopFocusBeneficiaries", Number.isFinite(Number(latestSize.beneficiary_count)) ? `${fmt.money(Number(latestSize.beneficiary_count))} 人` : "--");
  setText("desktopFocusBeneficiariesNote", Number.isFinite(Number(latestSize.beneficiary_change_pct)) ? `月變化 ${fmt.pct(Number(latestSize.beneficiary_change_pct))}` : "--");
  setText("desktopFocusAum", Number.isFinite(aumMillion) ? `${fmt.money(aumMillion / 100)} 億` : "--");
  setText("desktopFocusAumNote", latestSize.month || "--");

  const holdings = freshnessModel.holdingsData || {};
  const top10 = holdings.top10 || [];
  const top10Total = top10.reduce((sum, row) => sum + Number(row.weight_pct || 0), 0);
  setText("desktopFocusTop10", top10.length ? fmt.pct(top10Total) : "--");
  setText("desktopFocusTop10Note", holdings.data_date ? `資料日 ${holdings.data_date}` : "--");
  setText("desktopFocusTopHolding", top10[0] ? `${top10[0].name} ${top10[0].code || ""}` : "--");
  setText("desktopFocusTopHoldingNote", top10[0] ? fmt.pct(Number(top10[0].weight_pct || 0)) : "--");
}

function calcEstimatedDividendCash(dividend, position) {
  const dividendPerShare = Number(dividend.dividend_per_share || 0);
  const dividendShares = dividend.ex_date ? calcSharesOnDate(state.trades || [], dividend.ex_date) : position.holdingShares;
  return dividendShares * dividendPerShare;
}

function calcYearlyDividendTotal(year) {
  return (state.data.dividends || []).reduce((sum, dividend) => {
    const exDate = String(dividend.ex_date || "");
    if (!exDate.startsWith(String(year))) return sum;
    const shares = calcSharesOnDate(state.trades || [], exDate);
    return sum + shares * Number(dividend.dividend_per_share || 0);
  }, 0);
}

function calcYearly54cTotal(year) {
  return (state.data.dividends || []).reduce((sum, dividend) => {
    const exDate = String(dividend.ex_date || "");
    if (!exDate.startsWith(String(year))) return sum;
    const shares = calcSharesOnDate(state.trades || [], exDate);
    return sum + shares * Number(dividend.estimated_54c_per_share || 0);
  }, 0);
}

function renderDesktopModuleCards(model) {
  const dividendPerShare = Number(model.dividend.dividend_per_share || 0);
  const estimatedDividendCash = calcEstimatedDividendCash(model.dividend, model.position);
  const holdings = model.freshnessModel.holdingsData || {};
  const top10 = holdings.top10 || [];
  const latestYear = String(model.latestForPrice?.date || model.latest?.date || new Date().getFullYear()).slice(0, 4);
  const yearlyDividend = calcYearlyDividendTotal(latestYear);
  const yearly54c = calcYearly54cTotal(latestYear);
  const integrityWarnings = model.freshnessModel.integrity?.warnings || [];
  const signalSummary = model.signals.level === "green"
    ? "所有數據正常"
    : formatStatusShort({ className: model.signals.level }, Math.max(1, integrityWarnings.length));
  const moduleCards = document.querySelectorAll(".desktop-module-card");
  const moduleLabels = [
    ["每月健康檢查", "12 項", "前往檢視"],
    ["季度配息 / 54C", dividendPerShare ? `${fmt.money(dividendPerShare, 2)} 元` : "--", "前往檢視"],
    ["持股檢視", top10[0] ? `${top10[0].name} ${top10[0].code || ""}` : "--", "前往檢視"],
    ["年度稅務總覽", `$${fmt.money(yearlyDividend)}`, "前往檢視"],
    ["燈號設定", signalText(model.signals.level), "前往設定"],
  ];
  moduleLabels.forEach(([title, note, button], index) => {
    const card = moduleCards[index];
    if (!card) return;
    const heading = card.querySelector("h4");
    const paragraph = card.querySelector("p");
    const action = card.querySelector("a");
    if (heading) heading.textContent = title;
    if (paragraph) paragraph.textContent = note;
    if (action) action.textContent = button;
  });

  setText("desktopModuleMonthly", "正常 12 項");
  setText("desktopModuleDividendCash", `本季估 $${fmt.money(estimatedDividendCash)}`);
  setText("desktopModuleHoldingWeight", top10[0] ? fmt.pct(Number(top10[0].weight_pct || 0)) : "--");
  setText("desktopModule54c", `54C 估算 $${fmt.money(yearly54c)}`);
  setText("desktopModuleSignalReason", signalSummary);
}

function desktopCompactStatusLabel(status) {
  return formatStatusShort(status);
}

function setDesktopStatusRow(prefix, status, detail) {
  const row = $(`${prefix}Status`)?.closest(".desktop-status-row");
  if (row) row.dataset.status = status.className || "unknown";
  setText(`${prefix}Status`, desktopCompactStatusLabel(status));
  setText(`${prefix}Date`, detail || status.note || "--");
}

function renderDesktopDataStatusCompact(latest, dividend, model) {
  const marketDate = model.latestMarket?.date || latest.date;
  const warningCount = model.integrity?.warnings?.length || 0;
  setDesktopStatusRow("desktopFreshDaily", model.daily, marketDate || "--");
  setDesktopStatusRow("desktopFreshMonthly", model.monthly, model.latestMonthly.month || "--");
  setDesktopStatusRow("desktopFreshDividend", model.dividend, dividend.ex_date ? model.dividend.note : "--");
  setDesktopStatusRow("desktopFreshHoldings", model.holdings, model.holdingsData.data_date || "--");
  setDesktopStatusRow("desktopFreshFetched", model.fetched, model.fetchedAtDisplay || "--");
  setDesktopStatusRow("desktopFreshIntegrity", model.integrity.status, warningCount ? `${warningCount} 項` : "關鍵欄位完整");
}

function renderHomeFocus(position, latest, dividend, totalReturn, totalCost) {
  const totalReturnRate = totalCost ? (totalReturn / totalCost) * 100 : 0;
  setText("homeTotalReturn", `$${fmt.money(totalReturn)}`);
  setText("homeTotalReturnRate", `${fmt.pct(totalReturnRate)} / 含息估算`);
  $("homeTotalReturn")?.classList.toggle("negative", totalReturn < 0);
  $("homeTotalReturn")?.classList.toggle("positive", totalReturn >= 0);

  const dividendPerShare = Number(dividend.dividend_per_share || 0);
  const dividendShares = dividend.ex_date ? calcSharesOnDate(state.trades || [], dividend.ex_date) : position.holdingShares;
  const estimatedDividendCash = dividendShares * dividendPerShare;
  const estimated54c = dividendShares * Number(dividend.estimated_54c_per_share || 0);
  const settings = getAppSignalSettings();
  const premiumThreshold = Number(settings.single54cThreshold ?? HEALTH_PREMIUM_THRESHOLD);
  const premiumRate = Number(settings.supplementalPremiumRatePct ?? HEALTH_PREMIUM_RATE * 100) / 100;
  const healthPremium = estimated54c >= premiumThreshold ? estimated54c * premiumRate : 0;

  setText("homeLatestDividend", dividendPerShare ? `${fmt.money(dividendPerShare, 2)} 元` : "--");
  setText("homeLatestDividendDate", dividend.ex_date ? `除息 ${dividend.ex_date} / 估 $${fmt.money(estimatedDividendCash)}` : "--");
  setText("homeLatest54c", `$${fmt.money(estimated54c)}`);
  setText("homeLatest54cNote", Number(dividend.dividend_income_pct) ? `股利所得 ${fmt.pct(Number(dividend.dividend_income_pct))}` : "本次股利所得 0%");
  setText("homePremiumWatch", healthPremium > 0 ? `$${fmt.money(healthPremium)}` : "未達");
  setText("homePremiumNote", `門檻 $${fmt.money(premiumThreshold)}`);

  const sizeRows = (state.data.monthly_history || state.data.monthly_size || [])
    .filter((row) => row.month && (row.aum_million_twd != null || row.aum_100m_twd != null || row.beneficiary_count != null))
    .sort((a, b) => String(a.month).localeCompare(String(b.month)));
  const latestSize = sizeRows[sizeRows.length - 1] || {};
  const aumMillion = Number(latestSize.aum_million_twd || Number(latestSize.aum_100m_twd) * 100);
  setText("homeAum", Number.isFinite(aumMillion) ? `${fmt.money(aumMillion / 100)} 億` : "--");
  setText("homeAumMonth", latestSize.month || "--");
  setText("homeBeneficiaries", Number.isFinite(Number(latestSize.beneficiary_count)) ? `${fmt.money(Number(latestSize.beneficiary_count))} 人` : "--");
  setText(
    "homeBeneficiaryChange",
    Number.isFinite(Number(latestSize.beneficiary_change_pct)) ? `月變化 ${fmt.pct(Number(latestSize.beneficiary_change_pct))}` : "--"
  );

  const holdings = state.data.holdings || {};
  const top10 = holdings.top10 || [];
  const top10Total = top10.reduce((sum, row) => sum + Number(row.weight_pct || 0), 0);
  setText("homeTop10Total", top10.length ? fmt.pct(top10Total) : "--");
  setText("homeTop10Date", holdings.data_date ? `資料日 ${holdings.data_date}` : "--");
  setText("homeTopHolding", top10[0] ? `${top10[0].name} ${top10[0].code || ""}` : "--");
  setText("homeTopHoldingWeight", top10[0] ? fmt.pct(Number(top10[0].weight_pct || 0)) : "--");
}

function bindTradeForm() {
  document.querySelectorAll(".side-toggle button").forEach((button) => {
    button.addEventListener("click", () => {
      state.tradeAction = button.dataset.action;
      document.querySelectorAll(".side-toggle button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
    });
  });

  $("tradeForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const trade = {
      id: state.editingTradeId || `trade-${Date.now()}`,
      trade_date: normalizeTradeDate($("tradeDateInput").value),
      action: state.tradeAction,
      shares: Number($("tradeSharesInput").value || 0),
      price: Number($("tradePriceInput").value || 0),
      fee: 0,
      tax: 0,
      note_type: $("tradeNoteTypeInput").value,
      note: $("tradeNoteInput").value.trim(),
    };
    if (!trade.trade_date || !trade.shares || !trade.price) return;
    const isEditing = Boolean(state.editingTradeId);
    if (isEditing) {
      state.trades = state.trades.map((item) => (item.id === state.editingTradeId ? trade : item));
      state.editingTradeId = "";
      setText("tradeSubmitButton", "新增交易");
    } else {
      if (requestStreamlitTradeAppend(trade)) {
        const submitButton = $("tradeSubmitButton");
        if (submitButton) {
          submitButton.disabled = true;
          submitButton.classList.add("is-loading");
          submitButton.textContent = "寫入中...";
          window.setTimeout(() => {
            submitButton.disabled = false;
            submitButton.classList.remove("is-loading");
            submitButton.textContent = "新增交易";
            alert("寫入逾時，請檢查 Streamlit 後端是否收到 append_trade request");
          }, 10000);
        }
        return;
      }
      state.trades = [...state.trades, trade];
    }
    state.trades = state.trades.sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date)));
    saveTrades({ syncRemote: false, reason: isEditing ? "trade-edit" : "trade-add" });
    $("tradeForm").reset();
    state.tradeAction = "buy";
    document.querySelectorAll(".side-toggle button").forEach((item) => item.classList.remove("active"));
    document.querySelector('.side-toggle button[data-action="buy"]').classList.add("active");
    render();
  });

  $("exportTradesButton").addEventListener("click", exportTradesCsv);
  $("importTradesInput").addEventListener("change", importTrades);
  $("syncTradesButton")?.addEventListener("click", () => {
    const button = $("syncTradesButton");
    if (button) {
      button.disabled = true;
      button.classList.add("is-loading");
      button.textContent = "同步中...";
    }
    if (!requestStreamlitTradeSync(state.trades, "manual-trade-sync")) {
      if (button) {
        button.disabled = false;
        button.classList.remove("is-loading");
        button.textContent = "同步到雲端";
      }
      alert("目前環境無法直接同步到雲端，請先匯出資料備份。");
    }
  });
  $("downloadTemplateButton").addEventListener("click", downloadTradeTemplate);
}

function saveTrades(options = {}) {
  localStorage.setItem("00919_trades", JSON.stringify(state.trades));
  if (options.syncRemote) {
    requestStreamlitTradeSync(state.trades, options.reason || "trade-save");
  }
}

function renderTradeTable(position, latest) {
  const body = $("tradeTableBody");
  if (!body) return;
  const sorted = [...state.trades].sort((a, b) => String(b.trade_date).localeCompare(String(a.trade_date)));
  body.innerHTML = sorted
    .map((trade) => {
      const shares = Number(trade.shares || 0);
      const price = Number(trade.price || 0);
      const gross = shares * price;
      const actionLabel = trade.action === "sell" ? "賣出" : "買入";
      return `
        <tr>
          <td><span class="trade-badge ${trade.action === "sell" ? "sell" : "buy"}">${actionLabel}</span></td>
          <td>${trade.trade_date || "--"}</td>
          <td>${fmt.money(shares)} 股</td>
          <td>${fmt.money(price, 2)}</td>
          <td>$${fmt.money(gross)}</td>
          <td>${escapeHtml(trade.note_type || "")}</td>
          <td>${escapeHtml(trade.note || "")}</td>
          <td>
            <div class="row-actions">
              <button class="edit-trade" type="button" data-id="${trade.id || ""}">編輯</button>
              <button class="delete-trade" type="button" data-id="${trade.id || ""}">刪除</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  body.querySelectorAll(".edit-trade").forEach((button) => {
    button.addEventListener("click", () => {
      const target = state.trades.find((trade) => trade.id === button.dataset.id);
      if (!target) return;
      state.editingTradeId = target.id;
      state.tradeAction = target.action;
      document.querySelectorAll(".side-toggle button").forEach((item) => item.classList.remove("active"));
      document.querySelector(`.side-toggle button[data-action="${target.action}"]`).classList.add("active");
      $("tradeDateInput").value = normalizeTradeDate(target.trade_date);
      $("tradeSharesInput").value = target.shares || "";
      $("tradePriceInput").value = target.price || "";
      $("tradeNoteTypeInput").value = target.note_type || "其他";
      $("tradeNoteInput").value = target.note || "";
      setText("tradeSubmitButton", "更新交易");
      $("tradeForm").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });

  body.querySelectorAll(".delete-trade").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.id;
      state.trades = state.trades.filter((trade) => trade.id !== id);
      saveTrades({ syncRemote: true, reason: "trade-delete" });
      render();
    });
  });

  const marketPrice = Number(latest.market_price || 0);
  const marketValue = position.holdingShares * marketPrice;
  const unrealizedPnl = marketValue - position.totalCost;
  const totalReturn = unrealizedPnl + position.cumulativeDividend + position.realizedPnl;
  setText("tradeStatShares", `${fmt.money(position.holdingShares)} 股`);
  setText("tradeStatAvgCost", fmt.money(position.avgCost, 2));
  setText("tradeStatCost", `$${fmt.money(position.totalCost)}`);
  setText("tradeStatDividend", `$${fmt.money(position.cumulativeDividend)}`);
  setText("tradeStatMarketValue", `$${fmt.money(marketValue)}`);
  setText("tradeStatPnl", `$${fmt.money(unrealizedPnl)}`);
  setText("tradeStatTotalReturn", `$${fmt.money(totalReturn)}`);
  $("tradeStatPnl").className = unrealizedPnl >= 0 ? "positive" : "negative";
  $("tradeStatTotalReturn").className = totalReturn >= 0 ? "positive" : "negative";
}

function renderQuarterlyDividends(dividends, trades) {
  const rows = calcDividendRows(dividends, trades);
  const latest = rows[0];

  if (!latest) {
    setText("latestDividendExDate", "--");
    setText("latestDividendPayDate", "發放日 --");
    setText("latestDividendPerShare", "--");
    setText("latestDividendShares", "--");
    setText("latestDividendCash", "--");
    setText("latestDividend54c", "--");
    setText("latestDividend54cNote", "股利所得比例 --");
    setText("latestDividendHealth", "--");
    const body = $("dividendTableBody");
    if (body) body.innerHTML = "<tr><td colspan='10'>尚無歷史配息資料</td></tr>";
    const yearStats = $("dividendYearStats");
    if (yearStats) yearStats.innerHTML = "<div class='empty'>尚無年度統計</div>";
    return;
  }

  setText("latestDividendExDate", latest.exDate || "--");
  setText("latestDividendPayDate", `發放日 ${latest.payDate || "--"}`);
  setText("latestDividendPerShare", `${fmt.money(latest.perShare, 2)} 元`);
  setText("latestDividendShares", `${fmt.money(latest.shares)} 股`);
  setText("latestDividendCash", `$${fmt.money(latest.cash)}`);
  setText("latestDividend54c", `$${fmt.money(latest.estimated54c)}`);
  setText("latestDividend54cNote", `股利所得比例 ${fmt.pct(latest.dividendIncomePct)}`);
  setText("latestDividendHealth", latest.healthPremium > 0 ? `$${fmt.money(latest.healthPremium)}` : "未達觀察門檻");

  const body = $("dividendTableBody");
  if (body) {
    body.innerHTML = rows
      .map((row) => {
        const healthText = row.healthPremium > 0
          ? `<span class="dividend-risk">$${fmt.money(row.healthPremium)}</span>`
          : `<span class="dividend-ok">未達</span>`;
        return `
          <tr>
            <td>${row.exDate || "--"}</td>
            <td>${row.payDate || "--"}</td>
            <td>${fmt.money(row.perShare, 2)}</td>
            <td>${fmt.pct(row.dividendIncomePct)}</td>
            <td>${fmt.pct(row.equalizationPct)}</td>
            <td>${fmt.pct(row.capitalGainPct)}</td>
            <td>${fmt.money(row.shares)} 股</td>
            <td>$${fmt.money(row.cash)}</td>
            <td>$${fmt.money(row.estimated54c)}</td>
            <td>${healthText}</td>
          </tr>
        `;
      })
      .join("");
  }

  renderDividendYearStats(rows);
}

function calcDividendRows(dividends, trades) {
  const sortedTrades = [...trades].sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date)));
  return [...dividends]
    .sort((a, b) => String(b.ex_date).localeCompare(String(a.ex_date)))
    .map((dividend) => {
      const exDate = dividend.ex_date || "";
      const shares = calcSharesOnDate(sortedTrades, exDate);
      const perShare = Number(dividend.dividend_per_share || 0);
      const dividendIncomePct = Number(dividend.dividend_income_pct || 0);
      const estimated54cPerShare = Number(dividend.estimated_54c_per_share || 0);
      const estimated54c = shares * estimated54cPerShare;
      return {
        exDate,
        payDate: dividend.pay_date || "",
        perShare,
        dividendIncomePct,
        equalizationPct: Number(dividend.equalization_pct || 0),
        capitalGainPct: Number(dividend.capital_gain_pct || 0),
        shares,
        cash: shares * perShare,
        estimated54c,
        healthPremium: estimated54c >= 20000 ? estimated54c * 0.0211 : 0,
      };
    });
}

function renderDividendYearStats(rows) {
  const target = $("dividendYearStats");
  if (!target) return;
  const grouped = new Map();
  rows.forEach((row) => {
    const year = (row.exDate || "").slice(0, 4) || "未分類";
    if (!grouped.has(year)) {
      grouped.set(year, { year, cash: 0, estimated54c: 0, healthPremium: 0, count: 0 });
    }
    const item = grouped.get(year);
    item.cash += row.cash;
    item.estimated54c += row.estimated54c;
    item.healthPremium += row.healthPremium;
    item.count += 1;
  });

  target.innerHTML = Array.from(grouped.values())
    .sort((a, b) => String(b.year).localeCompare(String(a.year)))
    .map((item) => `
      <article class="yearly-stat">
        <strong>${item.year}</strong>
        <dl>
          <dt>配息次數</dt><dd>${item.count} 次</dd>
          <dt>配息估算</dt><dd>$${fmt.money(item.cash)}</dd>
          <dt>54C 估算</dt><dd>$${fmt.money(item.estimated54c)}</dd>
          <dt>補充保費</dt><dd>${item.healthPremium > 0 ? `$${fmt.money(item.healthPremium)}` : "未達"}</dd>
        </dl>
      </article>
    `)
    .join("");
}

function exportTradesCsv() {
  const rows = [
    ["trade_date", "action", "shares", "price", "note_type", "note"],
    ...state.trades.map((trade) => [
      trade.trade_date,
      trade.action,
      trade.shares,
      trade.price,
      trade.note_type || "",
      trade.note || "",
    ]),
  ];
  downloadCsv(rows, `00919_trades_${new Date().toISOString().slice(0, 10)}.csv`);
}

function downloadTradeTemplate() {
  const rows = [
    ["trade_date", "action", "shares", "price", "note_type", "note"],
    ["2026-01-15", "buy", "5000", "24.00", "薪資投入", "範例：請刪除或覆蓋"],
    ["2026-04-14", "buy", "1000", "25.00", "股息再投入", "範例：配息再投入"],
  ];
  downloadCsv(rows, "00919_trades_template.csv");
}

function downloadCsv(rows, filename) {
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\r\n");
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function importTrades(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const imported = normalizeTrades(parseTradesCsv(String(reader.result || "")));
      state.trades = mergeTrades(state.trades, imported).sort((a, b) =>
        String(a.trade_date).localeCompare(String(b.trade_date))
      );
      saveTrades({ syncRemote: true, reason: "trade-import" });
      render();
    } catch (error) {
      alert(`匯入失敗：${error.message}`);
    } finally {
      event.target.value = "";
    }
  };
  reader.readAsText(file, "utf-8");
}

function mergeTrades(existing, imported) {
  const merged = [...existing];
  const keys = new Set(existing.map(tradeKey));
  imported.forEach((trade) => {
    const key = tradeKey(trade);
    if (keys.has(key)) return;
    merged.push(trade);
    keys.add(key);
  });
  return merged;
}

function tradeKey(trade) {
  return [
    trade.trade_date || "",
    trade.action || "",
    Number(trade.shares || 0),
    Number(trade.price || 0).toFixed(4),
    trade.note_type || "",
    trade.note || "",
  ].join("|");
}

function tradeListKey(trades = []) {
  return [...trades]
    .map(tradeKey)
    .sort()
    .join("||");
}

function parseTradesCsv(text) {
  const rows = parseCsv(text);
  if (rows.length < 2) return [];
  const headers = rows[0].map((header) => header.trim());
  const required = ["trade_date", "action", "shares", "price"];
  const missing = required.filter((name) => !headers.includes(name));
  if (missing.length) {
    throw new Error(`CSV 缺少欄位：${missing.join(", ")}`);
  }
  return rows
    .slice(1)
    .filter((row) => row.some((cell) => String(cell).trim()))
    .map((row, index) => {
      const record = {};
      headers.forEach((header, headerIndex) => {
        record[header] = row[headerIndex] ?? "";
      });
      return {
        id: record.id || `trade-import-${Date.now()}-${index}`,
        trade_date: normalizeTradeDate(record.trade_date),
        action: String(record.action || "buy").toLowerCase() === "sell" ? "sell" : "buy",
        shares: Number(String(record.shares || "0").replaceAll(",", "")),
        price: Number(String(record.price || "0").replaceAll(",", "")),
        fee: Number(String(record.fee || "0").replaceAll(",", "")),
        tax: Number(String(record.tax || "0").replaceAll(",", "")),
        note_type: record.note_type || "其他",
        note: record.note || "",
      };
    });
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  if (rows[0]?.[0]?.charCodeAt(0) === 0xfeff) rows[0][0] = rows[0][0].slice(1);
  return rows;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function calcPosition(trades, dividends) {
  const sortedTrades = [...trades].sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date)));
  const firstTradeDate = sortedTrades[0]?.trade_date || "";
  let holdingShares = 0;
  let totalCost = 0;
  let realizedPnl = 0;

  sortedTrades.forEach((trade) => {
    const shares = Number(trade.shares || 0);
    const price = Number(trade.price || 0);
    const fee = Number(trade.fee || 0);
    const tax = Number(trade.tax || 0);
    if (trade.action === "sell") {
      const avgCostBeforeSell = holdingShares ? totalCost / holdingShares : 0;
      const costBasis = avgCostBeforeSell * shares;
      const proceeds = shares * price - fee - tax;
      holdingShares -= shares;
      totalCost -= costBasis;
      realizedPnl += proceeds - costBasis;
    } else {
      holdingShares += shares;
      totalCost += shares * price + fee;
    }
  });

  const cumulativeDividend = dividends.reduce((sum, dividend) => {
    const sharesOnExDate = calcSharesOnDate(sortedTrades, dividend.ex_date);
    return sum + sharesOnExDate * Number(dividend.dividend_per_share || 0);
  }, 0);

  return {
    holdingShares,
    totalCost,
    avgCost: holdingShares ? totalCost / holdingShares : 0,
    cumulativeDividend,
    firstTradeDate,
    realizedPnl,
  };
}

function calcSharesOnDate(sortedTrades, date) {
  return sortedTrades
    .filter((trade) => trade.trade_date <= date)
    .reduce((shares, trade) => {
      const amount = Number(trade.shares || 0);
      return trade.action === "sell" ? shares - amount : shares + amount;
    }, 0);
}

function scale(value, min, max, outMin, outMax) {
  if (max === min) return (outMin + outMax) / 2;
  return outMin + ((value - min) / (max - min)) * (outMax - outMin);
}

function pathFor(rows, xFn, yFn) {
  return rows
    .map((row, index) => `${index === 0 ? "M" : "L"} ${xFn(row).toFixed(2)} ${yFn(row).toFixed(2)}`)
    .join(" ");
}

function filterRowsByRange(allRows, range) {
  const cleanRows = allRows.filter(
    (row) => Number.isFinite(Number(row.market_price)) && Number.isFinite(Number(row.nav))
  );
  if (range === "week") {
    return cleanRows.slice(-5).map((row) => ({ ...row, period_label: row.date, period_type: "日" }));
  }
  if (range === "month") {
    return cleanRows.slice(-22).map((row) => ({ ...row, period_label: row.date, period_type: "日" }));
  }
  if (range === "year") {
    return aggregateRows(cleanRows.slice(-252), "month");
  }
  return aggregateRows(cleanRows, "month");
}

function aggregateRows(rows, mode) {
  const groups = new Map();
  rows.forEach((row) => {
    const key = mode === "week" ? getWeekKey(row.date) : row.date.slice(0, 7);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  });

  return Array.from(groups.entries()).map(([key, items]) => {
    const sorted = [...items].sort((a, b) => a.date.localeCompare(b.date));
    const last = sorted[sorted.length - 1];
    const volumeLots = sorted.reduce((sum, row) => sum + Number(row.volume_lots || 0), 0);
    return {
      ...last,
      date: key,
      period_label: mode === "week" ? `${key} 週` : key,
      period_type: mode === "week" ? "週" : "月",
      period_start: sorted[0].date,
      period_end: last.date,
      source_dates: sorted.length,
      volume_lots: volumeLots,
      volume_shares: sorted.reduce((sum, row) => sum + Number(row.volume_shares || 0), 0),
      premium_discount_pct_avg:
        sorted.reduce((sum, row) => sum + Number(row.premium_discount_pct || 0), 0) / sorted.length,
    };
  });
}

function getWeekKey(isoDate) {
  const date = new Date(`${isoDate}T00:00:00`);
  const day = date.getDay() || 7;
  date.setDate(date.getDate() + 4 - day);
  const yearStart = new Date(date.getFullYear(), 0, 1);
  const weekNo = Math.ceil(((date - yearStart) / 86400000 + 1) / 7);
  return `${date.getFullYear()}-W${String(weekNo).padStart(2, "0")}`;
}

function drawChart(allRows, range = "month", targetId = "mainChart") {
  const rows = allRows
    ? filterRowsByRange(allRows, range)
    : [];

  const chart = $(targetId);
  if (!chart) return;
  if (!rows.length) {
    chart.innerHTML = "<div class='empty'>尚無每日資料</div>";
    return;
  }

  const isMobile = window.matchMedia("(max-width: 760px)").matches;
  const isDesktopHome = targetId === "desktopMainChart";
  const width = isMobile ? 390 : 1120;
  const height = isMobile ? 280 : isDesktopHome ? 352 : 420;
  const pad = isMobile
    ? { top: 24, right: 34, bottom: 46, left: 38 }
    : isDesktopHome
      ? { top: 22, right: 54, bottom: 46, left: 48 }
      : { top: 28, right: 54, bottom: 72, left: 48 };
  const priceColor = isDesktopHome ? "#10b981" : "#1f5fbf";
  const navColor = isDesktopHome ? "#0ea5e9" : "#d65a3a";
  const discountColor = "#8b5cf6";
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const prices = rows.flatMap((row) => [Number(row.market_price), Number(row.nav)]);
  const priceMin = Math.min(...prices) - 0.15;
  const priceMax = Math.max(...prices) + 0.15;
  const discountValues = rows.map((row) => Number(row.premium_discount_pct || 0));
  const discountMin = Math.min(-1, ...discountValues) - 0.1;
  const discountMax = Math.max(1, ...discountValues) + 0.1;
  const volumeMax = Math.max(...rows.map((row) => Number(row.volume_lots || 0)), 1);
  const barBase = pad.top + plotH;
  const x = (_, index) => pad.left + (index / Math.max(rows.length - 1, 1)) * plotW;
  const yPrice = (value) => scale(value, priceMin, priceMax, pad.top + plotH, pad.top);
  const yDiscount = (value) => scale(value, discountMin, discountMax, pad.top + plotH, pad.top);
  const marketPath = pathFor(rows, (row) => x(row, rows.indexOf(row)), (row) => yPrice(Number(row.market_price)));
  const navPath = pathFor(rows, (row) => x(row, rows.indexOf(row)), (row) => yPrice(Number(row.nav)));
  const discountPath = pathFor(
    rows,
    (row) => x(row, rows.indexOf(row)),
    (row) => yDiscount(Number(row.premium_discount_pct || 0))
  );

  const grid = [0, 1, 2, 3, 4].map((i) => {
    const yy = pad.top + (plotH / 4) * i;
    const value = priceMax - ((priceMax - priceMin) / 4) * i;
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="14" y="${yy + 4}">${value.toFixed(2)}</text>
    `;
  });

  const rightAxis = [discountMin, 0, discountMax].map((value) => {
    const yy = yDiscount(value);
    return `<text class="axis-text" x="${width - pad.right + 16}" y="${yy + 4}">${value.toFixed(1)}%</text>`;
  });

  const bars = rows.map((row, index) => {
    const barW = Math.min(isMobile ? 18 : 58, Math.max(isMobile ? 3 : 8, plotW / rows.length - (isMobile ? 2 : 6)));
    const barH = scale(Number(row.volume_lots || 0), 0, volumeMax, 0, plotH * (isMobile ? 0.15 : 0.18));
    const xx = x(row, index) - barW / 2;
    return `<rect x="${xx.toFixed(2)}" y="${(barBase - barH).toFixed(2)}" width="${barW.toFixed(2)}" height="${barH.toFixed(2)}" fill="#c8d1d5" opacity="0.82" />`;
  });

  const zones = rows.map((row, index) => {
    const zoneW = plotW / Math.max(rows.length - 1, 1);
    const xx = Math.max(pad.left, x(row, index) - zoneW / 2);
    const widthValue = index === 0 || index === rows.length - 1 ? zoneW / 2 : zoneW;
    const payload = encodeURIComponent(JSON.stringify(row));
    return `<rect class="hover-zone" data-row="${payload}" data-x="${x(row, index).toFixed(2)}" x="${xx.toFixed(2)}" y="${pad.top}" width="${widthValue.toFixed(2)}" height="${plotH}" />`;
  });

  const points = rows
    .map((row, index) => {
      const xx = x(row, index);
      return `
        <circle class="chart-point" cx="${xx}" cy="${yPrice(Number(row.market_price))}" r="${isMobile ? 2.2 : 3.5}" fill="${priceColor}" />
        <circle class="chart-point" cx="${xx}" cy="${yPrice(Number(row.nav))}" r="${isMobile ? 2.2 : 3.5}" fill="${navColor}" />
        <circle class="chart-point" cx="${xx}" cy="${yDiscount(Number(row.premium_discount_pct || 0))}" r="${isMobile ? 2.2 : 3.5}" fill="${discountColor}" />
      `;
    })
    .join("");

  const labels = rows
    .filter((_, index) => index === 0 || index === rows.length - 1 || index % (isMobile ? 9 : 6) === 0)
    .map((row, index) => {
      const realIndex = rows.indexOf(row);
      return `<text class="axis-text" text-anchor="middle" x="${x(row, realIndex)}" y="${height - 30}">${row.date.slice(5)}</text>`;
    });

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="00919 市價淨值折溢價與成交量圖表">
      ${grid.join("")}
      ${rightAxis.join("")}
      ${bars.join("")}
      <line id="hoverGuide" class="hover-guide" x1="${pad.left}" x2="${pad.left}" y1="${pad.top}" y2="${barBase}" />
      <path d="${marketPath}" fill="none" stroke="${priceColor}" stroke-width="${isMobile ? 2.2 : 3}" />
      <path d="${navPath}" fill="none" stroke="${navColor}" stroke-width="${isMobile ? 2.2 : 3}" />
      <path d="${discountPath}" fill="none" stroke="${discountColor}" stroke-width="${isMobile ? 1.8 : 2.5}" stroke-dasharray="6 5" />
      ${points}
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${barBase}" y2="${barBase}" stroke="#bdc8cd" />
      ${labels.join("")}
      <text class="axis-text" x="${pad.left}" y="24">價格</text>
      <text class="axis-text" x="${width - pad.right - 32}" y="24">折溢價%</text>
      ${zones.join("")}
    </svg>
    <div id="chartTooltip" class="chart-tooltip"></div>
  `;

  bindChartTooltip(chart);
}

function drawDesktopTrendChart(allRows, range = "month") {
  drawChart(allRows, range, "desktopMainChart");
}

function drawMobileChart(allRows, range = "month") {
  const chart = $("mobileMainChart");
  if (!chart) return;
  const rows = allRows ? filterRowsByRange(allRows, range) : [];
  if (!rows.length) {
    chart.innerHTML = "<div class='empty'>尚無每日資料</div>";
    return;
  }

  const width = 390;
  const height = 226;
  const pad = { top: 18, right: 34, bottom: 38, left: 38 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const prices = rows.flatMap((row) => [Number(row.market_price), Number(row.nav)]);
  const priceMin = Math.min(...prices) - 0.15;
  const priceMax = Math.max(...prices) + 0.15;
  const discountValues = rows.map((row) => Number(row.premium_discount_pct || 0));
  const discountMin = Math.min(-1.2, ...discountValues) - 0.1;
  const discountMax = Math.max(1.2, ...discountValues) + 0.1;
  const volumeMax = Math.max(...rows.map((row) => Number(row.volume_lots || 0)), 1);
  const barBase = pad.top + plotH;
  const x = (_, index) => pad.left + (index / Math.max(rows.length - 1, 1)) * plotW;
  const yPrice = (value) => scale(value, priceMin, priceMax, pad.top + plotH, pad.top);
  const yDiscount = (value) => scale(value, discountMin, discountMax, pad.top + plotH, pad.top);
  const marketPath = pathFor(rows, (row) => x(row, rows.indexOf(row)), (row) => yPrice(Number(row.market_price)));
  const navPath = pathFor(rows, (row) => x(row, rows.indexOf(row)), (row) => yPrice(Number(row.nav)));
  const discountPath = pathFor(
    rows,
    (row) => x(row, rows.indexOf(row)),
    (row) => yDiscount(Number(row.premium_discount_pct || 0))
  );

  const grid = [0, 1, 2, 3].map((i) => {
    const yy = pad.top + (plotH / 3) * i;
    const value = priceMax - ((priceMax - priceMin) / 3) * i;
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="8" y="${yy + 4}">${value.toFixed(2)}</text>
    `;
  });

  const rightAxis = [discountMin, 0, discountMax].map((value) => {
    const yy = yDiscount(value);
    return `<text class="axis-text" x="${width - pad.right + 8}" y="${yy + 4}">${value.toFixed(1)}%</text>`;
  });

  const bars = rows.map((row, index) => {
    const barW = Math.min(12, Math.max(3, plotW / rows.length - 2));
    const barH = scale(Number(row.volume_lots || 0), 0, volumeMax, 0, plotH * 0.2);
    const xx = x(row, index) - barW / 2;
    return `<rect x="${xx.toFixed(2)}" y="${(barBase - barH).toFixed(2)}" width="${barW.toFixed(2)}" height="${barH.toFixed(2)}" fill="#cbd5e1" opacity="0.82" />`;
  });

  const labels = rows
    .filter((_, index) => index === 0 || index === rows.length - 1 || index % 8 === 0)
    .map((row) => {
      const realIndex = rows.indexOf(row);
      return `<text class="axis-text" text-anchor="middle" x="${x(row, realIndex)}" y="${height - 14}">${row.date.slice(5)}</text>`;
    });

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="00919 手機走勢圖">
      ${grid.join("")}
      ${rightAxis.join("")}
      ${bars.join("")}
      <path d="${marketPath}" fill="none" stroke="#10b981" stroke-width="2.5" />
      <path d="${navPath}" fill="none" stroke="#0ea5e9" stroke-width="2.5" />
      <path d="${discountPath}" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-dasharray="5 5" />
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${barBase}" y2="${barBase}" stroke="#cbd5e1" />
      ${labels.join("")}
    </svg>
  `;
}

hydrateInlineIcons();
hydrateDesktopIcons();
bindInputs();
loadData().catch((error) => {
  console.error(error);
  setText("signalLabel", "資料讀取失敗");
  setText(
    "signalReason",
    `${error.message || "未知錯誤"}。請確認已執行 python fetch_data.py，並透過 http://localhost:8787/index.html 開啟。`
  );
});

function bindChartTooltip(chart) {
  const tooltip = chart.querySelector("#chartTooltip");
  const guide = chart.querySelector("#hoverGuide");
  chart.querySelectorAll(".hover-zone").forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      const row = JSON.parse(decodeURIComponent(zone.dataset.row));
      const label = row.period_start
        ? `${row.period_label}（${row.period_start} 至 ${row.period_end}）`
        : row.date;
      const volumeLabel = row.period_type === "日" ? "成交量" : `${row.period_type}成交量`;
      tooltip.innerHTML = `
        <strong>${label}</strong>
        <div><span>市價</span><b>${fmt.money(Number(row.market_price), 2)}</b></div>
        <div><span>淨值</span><b>${fmt.money(Number(row.nav), 2)}</b></div>
        <div><span>期末折溢價</span><b>${fmt.pct(Number(row.premium_discount_pct))}</b></div>
        ${Number.isFinite(Number(row.premium_discount_pct_avg)) ? `<div><span>平均折溢價</span><b>${fmt.pct(Number(row.premium_discount_pct_avg))}</b></div>` : ""}
        <div><span>${volumeLabel}</span><b>${fmt.lots(Number(row.volume_lots))}</b></div>
      `;
      tooltip.classList.add("show");
      guide.classList.add("active");
      guide.setAttribute("x1", zone.dataset.x);
      guide.setAttribute("x2", zone.dataset.x);
    });
    zone.addEventListener("mousemove", (event) => {
      const box = chart.getBoundingClientRect();
      const left = Math.min(event.clientX - box.left + 16, box.width - 210);
      const top = Math.max(event.clientY - box.top - 18, 10);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    });
    zone.addEventListener("mouseleave", () => {
      tooltip.classList.remove("show");
      guide.classList.remove("active");
    });
  });
}

function renderQuarterlyDividends(dividends, trades) {
  const rows = calcDividendRows(dividends, trades);
  const latest = rows.find((row) => row.isTracked) || rows[0];

  if (!latest) {
    setText("latestDividendExDate", "--");
    setText("latestDividendPayDate", "發放日 --");
    setText("latestDividendPerShare", "--");
    setText("latestDividendShares", "--");
    setText("latestDividendCash", "--");
    setText("latestDividend54c", "--");
    setText("latestDividend54cNote", "股利所得比例 --");
    setText("latestDividendHealth", "--");
    const body = $("dividendTableBody");
    if (body) body.innerHTML = "<tr><td colspan='10'>尚無歷史配息資料</td></tr>";
    const chart = $("dividendYearChart");
    if (chart) chart.innerHTML = "<div class='empty'>尚無年度統計</div>";
    const yearStats = $("dividendYearStats");
    if (yearStats) yearStats.innerHTML = "<div class='empty'>尚無年度統計</div>";
    return;
  }

  setText("latestDividendExDate", latest.exDate || "--");
  setText("latestDividendPayDate", `發放日 ${latest.payDate || "--"}`);
  setText("latestDividendPerShare", `${fmt.money(latest.perShare, 2)} 元`);
  setText("latestDividendShares", latest.isTracked ? `${fmt.money(latest.shares)} 股` : "--");
  setText("latestDividendCash", latest.isTracked ? `$${fmt.money(latest.cash)}` : "--");
  setText("latestDividend54c", latest.isTracked ? `$${fmt.money(latest.estimated54c)}` : "--");
  setText("latestDividend54cNote", `股利所得比例 ${fmt.pct(latest.dividendIncomePct)}`);
  setText(
    "latestDividendHealth",
    latest.isTracked ? (latest.healthPremium > 0 ? `$${fmt.money(latest.healthPremium)}` : "未達觀察門檻") : "--"
  );

  const body = $("dividendTableBody");
  if (body) {
    body.innerHTML = rows
      .map((row) => {
        const sharesText = row.isTracked ? `${fmt.money(row.shares)} 股` : "";
        const cashText = row.isTracked ? `$${fmt.money(row.cash)}` : "";
        const estimated54cText = row.isTracked ? `$${fmt.money(row.estimated54c)}` : "";
        const healthText = !row.isTracked
          ? ""
          : row.healthPremium > 0
          ? `<span class="dividend-risk">$${fmt.money(row.healthPremium)}</span>`
          : `<span class="dividend-ok">未達</span>`;
        return `
          <tr>
            <td>${row.exDate || "--"}</td>
            <td>${row.payDate || "--"}</td>
            <td>${fmt.money(row.perShare, 2)}</td>
            <td>${fmt.pct(row.dividendIncomePct)}</td>
            <td>${fmt.pct(row.equalizationPct)}</td>
            <td>${fmt.pct(row.capitalGainPct)}</td>
            <td>${sharesText}</td>
            <td>${cashText}</td>
            <td>${estimated54cText}</td>
            <td>${healthText}</td>
          </tr>
        `;
      })
      .join("");
  }

  renderDividendYearStats(rows.filter((row) => row.isTracked));
}

function calcDividendRows(dividends, trades) {
  const sortedTrades = [...trades].sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date)));
  const trackStartDate = sortedTrades[0]?.trade_date || "";
  return [...dividends]
    .sort((a, b) => String(b.ex_date).localeCompare(String(a.ex_date)))
    .map((dividend) => {
      const exDate = dividend.ex_date || "";
      const isTracked = Boolean(trackStartDate && exDate >= trackStartDate);
      const shares = isTracked ? calcSharesOnDate(sortedTrades, exDate) : 0;
      const perShare = Number(dividend.dividend_per_share || 0);
      const dividendIncomePct = Number(dividend.dividend_income_pct || 0);
      const estimated54cPerShare = Number(dividend.estimated_54c_per_share || 0);
      const estimated54c = shares * estimated54cPerShare;
      return {
        exDate,
        payDate: dividend.pay_date || "",
        perShare,
        dividendIncomePct,
        equalizationPct: Number(dividend.equalization_pct || 0),
        capitalGainPct: Number(dividend.capital_gain_pct || 0),
        isTracked,
        shares,
        cash: shares * perShare,
        estimated54c,
        healthPremium: estimated54c >= HEALTH_PREMIUM_THRESHOLD ? estimated54c * HEALTH_PREMIUM_RATE : 0,
      };
    });
}

function renderDividendYearStats(rows) {
  const chart = $("dividendYearChart");
  const target = $("dividendYearStats");
  const grouped = new Map();
  rows.forEach((row) => {
    const year = (row.exDate || "").slice(0, 4) || "未分類";
    if (!grouped.has(year)) {
      grouped.set(year, { year, cash: 0, estimated54c: 0, healthPremium: 0, count: 0 });
    }
    const item = grouped.get(year);
    item.cash += row.cash;
    item.estimated54c += row.estimated54c;
    item.healthPremium += row.healthPremium;
    item.count += 1;
  });

  const items = Array.from(grouped.values()).sort((a, b) => String(a.year).localeCompare(String(b.year)));
  const maxCash = Math.max(...items.map((item) => item.cash), 1);

  if (chart) {
    chart.innerHTML = items.length
      ? items
          .map((item) => {
            const height = Math.max(3, (item.cash / maxCash) * 150);
            return `
              <div class="dividend-bar-item">
                <div class="dividend-bar-stack"><div class="dividend-bar" style="height:${height.toFixed(1)}px"></div></div>
                <div class="dividend-bar-value">$${fmt.money(item.cash)}</div>
                <div>${item.year}</div>
              </div>
            `;
          })
          .join("")
      : "<div class='empty'>追蹤起點後尚無年度配息</div>";
  }

  if (target) {
    target.innerHTML = items.length
      ? [...items]
          .reverse()
          .map((item) => `
            <article class="yearly-stat">
              <strong>${item.year}</strong>
              <dl>
                <dt>配息次數</dt><dd>${item.count} 次</dd>
                <dt>配息估算</dt><dd>$${fmt.money(item.cash)}</dd>
                <dt>54C 估算</dt><dd>$${fmt.money(item.estimated54c)}</dd>
                <dt>補充保費</dt><dd>${item.healthPremium > 0 ? `$${fmt.money(item.healthPremium)}` : "未達"}</dd>
              </dl>
            </article>
          `)
          .join("")
      : "<div class='empty'>追蹤起點後尚無年度統計</div>";
  }
}

function renderQuarterlyDividends(dividends, trades) {
  const rows = calcDividendRows(dividends, trades);
  const latest = rows.find((row) => row.isTracked) || rows[0];
  ensureDividendCompositionChart();

  if (!latest) {
    setText("latestDividendExDate", "--");
    setText("latestDividendPayDate", "發放日 --");
    setText("latestDividendPerShare", "--");
    setText("latestDividendShares", "--");
    setText("latestDividendCash", "--");
    setText("latestDividend54c", "--");
    setText("latestDividend54cNote", "股利所得比例 --");
    setText("latestDividendHealth", "--");
    const chart = $("dividendCompositionChart");
    if (chart) chart.innerHTML = "<div class='empty'>尚無配息組成資料</div>";
    renderDividendEstimateTable([]);
    return;
  }

  setText("latestDividendExDate", latest.exDate || "--");
  setText("latestDividendPayDate", `發放日 ${latest.payDate || "--"}`);
  setText("latestDividendPerShare", `${fmt.money(latest.perShare, 2)} 元`);
  setText("latestDividendShares", latest.isTracked ? `${fmt.money(latest.shares)} 股` : "--");
  setText("latestDividendCash", latest.isTracked ? `$${fmt.money(latest.cash)}` : "--");
  setText("latestDividend54c", latest.isTracked ? `$${fmt.money(latest.estimated54c)}` : "--");
  setText("latestDividend54cNote", `股利所得比例 ${fmt.pct(latest.dividendIncomePct)}`);
  setText(
    "latestDividendHealth",
    latest.isTracked ? (latest.healthPremium > 0 ? `$${fmt.money(latest.healthPremium)}` : "未達觀察門檻") : "--"
  );

  drawDividendCompositionChart(rows);
  renderDividendEstimateTable(rows);
}

function ensureDividendCompositionChart() {
  if ($("dividendCompositionChart")) return;
  const layout = document.querySelector(".quarterly-layout");
  if (!layout) return;
  const card = document.createElement("div");
  card.className = "dividend-composition-card";
  card.innerHTML = `
    <div class="dividend-composition-head">
      <div>
        <h4>每季配息組成</h4>
        <p>每季一根柱，柱高代表每股配息；顏色代表股利所得、收益平準金與資本利得占比。</p>
      </div>
      <div class="dividend-composition-legend">
        <span><i class="legend-dot income"></i>股利所得</span>
        <span><i class="legend-dot equalization"></i>收益平準金</span>
        <span><i class="legend-dot capital"></i>資本利得</span>
      </div>
    </div>
    <div id="dividendCompositionChart" class="dividend-composition-chart"></div>
  `;
  layout.parentNode.insertBefore(card, layout);
}

function drawDividendCompositionChart(rows) {
  const chart = $("dividendCompositionChart");
  if (!chart) return;
  const chronological = [...rows].sort((a, b) => String(a.exDate).localeCompare(String(b.exDate)));
  if (!chronological.length) {
    chart.innerHTML = "<div class='empty'>尚無配息組成資料</div>";
    return;
  }

  const width = Math.max(1120, chronological.length * 78 + 120);
  const height = 430;
  const pad = { top: 28, right: 70, bottom: 58, left: 58 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const maxDividend = Math.max(...chronological.map((row) => row.perShare), 1);
  const barW = 34;
  const x = (index) => pad.left + (index / Math.max(chronological.length - 1, 1)) * plotW;
  const yDividend = (value) => scale(value, 0, maxDividend * 1.15, pad.top + plotH, pad.top);
  const barBase = pad.top + plotH;
  const yearlyTotals = calcAnnualPerShareTotals(chronological);

  const yGrid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = maxDividend * 1.15 * ratio;
    const yy = yDividend(value);
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="16" y="${yy + 4}">${value.toFixed(2)}</text>
    `;
  });
  const percentAxis = [0, 25, 50, 75, 100].map((pct) => {
    const yy = scale(pct, 0, 100, barBase, pad.top);
    return `<text class="axis-text" x="${width - pad.right + 18}" y="${yy + 4}">${pct}%</text>`;
  });

  const bars = chronological.map((row, index) => {
    const xx = x(index) - barW / 2;
    const totalH = Math.max(4, barBase - yDividend(row.perShare));
    const incomeH = totalH * row.dividendIncomePct / 100;
    const equalizationH = totalH * row.equalizationPct / 100;
    const capitalH = totalH * row.capitalGainPct / 100;
    let top = barBase;
    const segments = [
      { h: incomeH, color: "#1f8f5f" },
      { h: equalizationH, color: "#d99b2b" },
      { h: capitalH, color: "#6f63c6" },
    ].map((seg) => {
      top -= seg.h;
      return `<rect x="${xx}" y="${top}" width="${barW}" height="${Math.max(0, seg.h)}" fill="${seg.color}" />`;
    }).join("");
    const payload = encodeURIComponent(JSON.stringify({ ...row, annualPerShare: yearlyTotals.get(row.year) || 0 }));
    return `
      <g>
        ${segments}
        <rect class="composition-hover" data-row="${payload}" x="${xx - 10}" y="${pad.top}" width="${barW + 20}" height="${plotH}" />
      </g>
    `;
  });

  const yearLabels = Array.from(groupRowsByYear(chronological).entries()).map(([year, yearRows]) => {
    const indexes = yearRows.map((row) => chronological.indexOf(row));
    const centerIndex = (Math.min(...indexes) + Math.max(...indexes)) / 2;
    return `<text class="axis-text" text-anchor="middle" x="${x(centerIndex)}" y="${height - 22}">${year}</text>`;
  });

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="00919 每季配息組成直條圖">
      ${yGrid.join("")}
      ${percentAxis.join("")}
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${barBase}" y2="${barBase}" stroke="#bdc8cd" />
      ${bars.join("")}
      ${yearLabels.join("")}
      <text class="axis-text" x="${pad.left}" y="20">每股配息</text>
      <text class="axis-text" x="${width - pad.right - 28}" y="20">占比</text>
    </svg>
    <div id="compositionTooltip" class="composition-tooltip"></div>
  `;
  bindDividendCompositionTooltip(chart);
}

function renderDividendEstimateTable(rows) {
  const table = document.querySelector(".dividend-table");
  if (!table) return;
  const annualTotals = calcAnnualPerShareTotals(rows);
  table.innerHTML = `
    <thead>
      <tr>
        <th>除息日</th>
        <th>發放日</th>
        <th>當時股數</th>
        <th>配息估算</th>
        <th>54C 估算</th>
        <th>補充保費</th>
        <th>年度配息統計</th>
      </tr>
    </thead>
    <tbody id="dividendTableBody">
      ${rows.map((row) => {
        const annualText = `${row.year} 每股 ${fmt.money(annualTotals.get(row.year) || 0, 2)} 元`;
        const healthText = !row.isTracked
          ? ""
          : row.healthPremium > 0
          ? `<span class="dividend-risk">$${fmt.money(row.healthPremium)}</span>`
          : `<span class="dividend-ok">未達</span>`;
        return `
          <tr>
            <td>${row.exDate || "--"}</td>
            <td>${row.payDate || "--"}</td>
            <td>${row.isTracked ? `${fmt.money(row.shares)} 股` : ""}</td>
            <td>${row.isTracked ? `$${fmt.money(row.cash)}` : ""}</td>
            <td>${row.isTracked ? `$${fmt.money(row.estimated54c)}` : ""}</td>
            <td>${healthText}</td>
            <td>${annualText}</td>
          </tr>
        `;
      }).join("")}
    </tbody>
  `;
}

function calcDividendRows(dividends, trades) {
  const sortedTrades = [...trades].sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date)));
  const trackStartDate = sortedTrades[0]?.trade_date || "";
  return [...dividends]
    .sort((a, b) => String(b.ex_date).localeCompare(String(a.ex_date)))
    .map((dividend) => {
      const exDate = dividend.ex_date || "";
      const isTracked = Boolean(trackStartDate && exDate >= trackStartDate);
      const shares = isTracked ? calcSharesOnDate(sortedTrades, exDate) : 0;
      const perShare = Number(dividend.dividend_per_share || 0);
      const estimated54c = shares * Number(dividend.estimated_54c_per_share || 0);
      return {
        exDate,
        payDate: dividend.pay_date || "",
        year: exDate.slice(0, 4) || "----",
        perShare,
        dividendIncomePct: Number(dividend.dividend_income_pct || 0),
        equalizationPct: Number(dividend.equalization_pct || 0),
        capitalGainPct: Number(dividend.capital_gain_pct || 0),
        isTracked,
        shares,
        cash: shares * perShare,
        estimated54c,
        healthPremium: estimated54c >= HEALTH_PREMIUM_THRESHOLD ? estimated54c * HEALTH_PREMIUM_RATE : 0,
      };
    });
}

function calcAnnualPerShareTotals(rows) {
  const totals = new Map();
  rows.forEach((row) => {
    totals.set(row.year, (totals.get(row.year) || 0) + row.perShare);
  });
  return totals;
}

function groupRowsByYear(rows) {
  const grouped = new Map();
  rows.forEach((row) => {
    if (!grouped.has(row.year)) grouped.set(row.year, []);
    grouped.get(row.year).push(row);
  });
  return grouped;
}

function bindDividendCompositionTooltip(chart) {
  const tooltip = chart.querySelector("#compositionTooltip");
  if (!tooltip) return;
  chart.querySelectorAll(".composition-hover").forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      const row = JSON.parse(decodeURIComponent(zone.dataset.row));
      tooltip.innerHTML = `
        <strong>${row.exDate} 每股 ${fmt.money(Number(row.perShare), 2)} 元</strong>
        <div><span>股利所得</span><b>${fmt.pct(Number(row.dividendIncomePct))}</b></div>
        <div><span>收益平準金</span><b>${fmt.pct(Number(row.equalizationPct))}</b></div>
        <div><span>資本利得</span><b>${fmt.pct(Number(row.capitalGainPct))}</b></div>
        <div><span>年度每股合計</span><b>${fmt.money(Number(row.annualPerShare), 2)} 元</b></div>
      `;
      tooltip.classList.add("show");
    });
    zone.addEventListener("mousemove", (event) => {
      const box = chart.getBoundingClientRect();
      const left = Math.min(event.clientX - box.left + 16, box.width - 250);
      const top = Math.max(event.clientY - box.top - 18, 10);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    });
    zone.addEventListener("mouseleave", () => tooltip.classList.remove("show"));
  });
}

function drawDividendCompositionChart(rows) {
  const chart = $("dividendCompositionChart");
  if (!chart) return;
  const chronological = [...rows].sort((a, b) => String(a.exDate).localeCompare(String(b.exDate)));
  if (!chronological.length) {
    chart.innerHTML = "<div class='empty'>尚無配息組成資料</div>";
    return;
  }

  const grouped = groupRowsByYear(chronological);
  const barW = Math.max(18, Math.min(34, 360 / Math.max(chronological.length, 1)));
  const quarterGap = barW + 12;
  const yearGap = 72;
  const pad = { top: 30, right: 72, bottom: 58, left: 58 };
  const plotH = 344;
  const height = pad.top + plotH + pad.bottom;
  const maxDividend = Math.max(...chronological.map((row) => row.perShare), 1);
  const yearlyTotals = calcAnnualPerShareTotals(chronological);

  let cursor = 0;
  const localPositions = new Map();
  const yearCentersLocal = [];
  Array.from(grouped.entries()).forEach(([year, yearRows], yearIndex) => {
    const start = cursor;
    yearRows.forEach((row, index) => {
      localPositions.set(row.exDate, cursor + index * quarterGap);
    });
    const end = cursor + Math.max(yearRows.length - 1, 0) * quarterGap;
    yearCentersLocal.push({ year, x: (start + end) / 2 });
    cursor = end + barW + yearGap;
    if (yearIndex === grouped.size - 1) cursor = end + barW;
  });

  const viewportWidth = chart.clientWidth || 1120;
  const plotAvailable = viewportWidth - pad.left - pad.right;
  const width = cursor <= plotAvailable ? viewportWidth : pad.left + cursor + pad.right;
  const centerOffset = cursor <= plotAvailable ? (plotAvailable - cursor) / 2 : 0;
  const xFor = (row) => centerOffset + pad.left + localPositions.get(row.exDate);
  const barBase = pad.top + plotH;
  const yDividend = (value) => scale(value, 0, maxDividend * 1.15, barBase, pad.top);

  const yGrid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = maxDividend * 1.15 * ratio;
    const yy = yDividend(value);
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="16" y="${yy + 4}">${value.toFixed(2)}</text>
    `;
  });
  const percentAxis = [0, 25, 50, 75, 100].map((pct) => {
    const yy = scale(pct, 0, 100, barBase, pad.top);
    return `<text class="axis-text" x="${width - pad.right + 18}" y="${yy + 4}">${pct}%</text>`;
  });

  const bars = chronological.map((row) => {
    const xx = xFor(row) - barW / 2;
    const totalH = Math.max(4, barBase - yDividend(row.perShare));
    const incomeH = totalH * row.dividendIncomePct / 100;
    const equalizationH = totalH * row.equalizationPct / 100;
    const capitalH = totalH * row.capitalGainPct / 100;
    let top = barBase;
    const segments = [
      { h: incomeH, color: "#1f8f5f" },
      { h: equalizationH, color: "#d99b2b" },
      { h: capitalH, color: "#6f63c6" },
    ].map((seg) => {
      top -= seg.h;
      return `<rect x="${xx}" y="${top}" width="${barW}" height="${Math.max(0, seg.h)}" fill="${seg.color}" />`;
    }).join("");
    const payload = encodeURIComponent(JSON.stringify({ ...row, annualPerShare: yearlyTotals.get(row.year) || 0 }));
    return `
      <g>
        ${segments}
        <rect class="composition-hover" data-row="${payload}" x="${xx - 8}" y="${pad.top}" width="${barW + 16}" height="${plotH}" />
      </g>
    `;
  });

  const yearLabels = yearCentersLocal.map(({ year, x }) =>
    `<text class="axis-text year-label" text-anchor="middle" x="${centerOffset + pad.left + x}" y="${height - 22}">${year}</text>`
  );

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="00919 每季配息組成直條圖">
      ${yGrid.join("")}
      ${percentAxis.join("")}
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${barBase}" y2="${barBase}" stroke="#bdc8cd" />
      ${bars.join("")}
      ${yearLabels.join("")}
      <text class="axis-text" x="${pad.left}" y="20">每股配息</text>
      <text class="axis-text" x="${width - pad.right - 28}" y="20">占比</text>
    </svg>
    <div id="compositionTooltip" class="composition-tooltip"></div>
  `;
  bindDividendCompositionTooltip(chart);
}

function buildDividendEstimateRows(rows) {
  const currentYear = String(new Date().getFullYear());
  return Array.from(groupRowsByYear(rows).entries())
    .sort(([yearA], [yearB]) => String(yearB).localeCompare(String(yearA)))
    .flatMap(([year, yearRows]) => {
      const sorted = [...yearRows].sort((a, b) => String(b.exDate).localeCompare(String(a.exDate)));
      const perShareTotal = sorted.reduce((sum, row) => sum + row.perShare, 0);
      const hasTracked = sorted.some((row) => row.isTracked);
      const shouldExpand = year === currentYear && hasTracked;
      if (!shouldExpand) {
        return [{ type: "annual", year, perShareTotal, count: sorted.length }];
      }
      return sorted
        .filter((row) => row.isTracked)
        .map((row, index) => ({
          type: "quarter",
          row,
          showAnnual: index === 0,
          perShareTotal,
          count: sorted.length,
        }));
    });
}

function buildDividendEstimateRows(rows) {
  const currentYear = String(new Date().getFullYear());
  return Array.from(groupRowsByYear(rows).entries())
    .sort(([yearA], [yearB]) => String(yearB).localeCompare(String(yearA)))
    .flatMap(([year, yearRows]) => {
      const sorted = [...yearRows].sort((a, b) => String(b.exDate).localeCompare(String(a.exDate)));
      const perShareTotal = sorted.reduce((sum, row) => sum + row.perShare, 0);
      const hasTracked = sorted.some((row) => row.isTracked);
      if (year !== currentYear || !hasTracked) {
        return [{ type: "annual", year, perShareTotal, count: sorted.length }];
      }
      return sorted
        .filter((row) => row.isTracked)
        .map((row, index) => ({
          type: "quarter",
          row,
          showAnnual: index === 0,
          perShareTotal,
          count: sorted.length,
        }));
    });
}

function drawDividendCompositionChart(rows) {
  const chart = $("dividendCompositionChart");
  if (!chart) return;
  const chronological = [...rows].sort((a, b) => String(a.exDate).localeCompare(String(b.exDate)));
  if (!chronological.length) {
    chart.innerHTML = "<div class='empty'>尚無配息組成資料</div>";
    return;
  }

  const grouped = groupRowsByYear(chronological);
  const barW = Math.max(18, Math.min(34, 360 / Math.max(chronological.length, 1)));
  const quarterGap = barW + 12;
  const yearGap = 72;
  const pad = { top: 30, right: 72, bottom: 58, left: 58 };
  const plotH = 344;
  const height = pad.top + plotH + pad.bottom;
  const maxDividend = Math.max(...chronological.map((row) => row.perShare), 1);
  const yearlyTotals = calcAnnualPerShareTotals(chronological);

  let cursor = 0;
  const localPositions = new Map();
  const yearCenters = [];
  Array.from(grouped.entries()).forEach(([year, yearRows], yearIndex) => {
    const start = cursor;
    yearRows.forEach((row, index) => {
      localPositions.set(row.exDate, cursor + index * quarterGap);
    });
    const end = cursor + Math.max(yearRows.length - 1, 0) * quarterGap;
    yearCenters.push({ year, x: (start + end) / 2 });
    cursor = end + barW + yearGap;
    if (yearIndex === grouped.size - 1) cursor = end + barW;
  });

  const viewportWidth = chart.clientWidth || 1120;
  const plotAvailable = viewportWidth - pad.left - pad.right;
  const width = cursor <= plotAvailable ? viewportWidth : pad.left + cursor + pad.right;
  const centerOffset = cursor <= plotAvailable ? (plotAvailable - cursor) / 2 : 0;
  const xFor = (row) => pad.left + centerOffset + localPositions.get(row.exDate);
  const barBase = pad.top + plotH;
  const yDividend = (value) => scale(value, 0, maxDividend * 1.15, barBase, pad.top);

  const yGrid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = maxDividend * 1.15 * ratio;
    const yy = yDividend(value);
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="16" y="${yy + 4}">${value.toFixed(2)}</text>
    `;
  });
  const percentAxis = [0, 25, 50, 75, 100].map((pct) => {
    const yy = scale(pct, 0, 100, barBase, pad.top);
    return `<text class="axis-text" x="${width - pad.right + 18}" y="${yy + 4}">${pct}%</text>`;
  });

  const bars = chronological.map((row) => {
    const xx = xFor(row) - barW / 2;
    const totalH = Math.max(4, barBase - yDividend(row.perShare));
    const incomeH = totalH * row.dividendIncomePct / 100;
    const equalizationH = totalH * row.equalizationPct / 100;
    const capitalH = totalH * row.capitalGainPct / 100;
    let top = barBase;
    const segments = [
      { h: incomeH, color: "#1f8f5f" },
      { h: equalizationH, color: "#d99b2b" },
      { h: capitalH, color: "#6f63c6" },
    ].map((seg) => {
      top -= seg.h;
      return `<rect x="${xx}" y="${top}" width="${barW}" height="${Math.max(0, seg.h)}" fill="${seg.color}" />`;
    }).join("");
    const payload = encodeURIComponent(JSON.stringify({ ...row, annualPerShare: yearlyTotals.get(row.year) || 0 }));
    return `
      <g>
        ${segments}
        <rect class="composition-hover" data-row="${payload}" x="${xx - 8}" y="${pad.top}" width="${barW + 16}" height="${plotH}" />
      </g>
    `;
  });

  const yearLabels = yearCenters.map(({ year, x }) =>
    `<text class="axis-text year-label" text-anchor="middle" x="${pad.left + centerOffset + x}" y="${height - 22}">${year}</text>`
  );

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="00919 每季配息組成直條圖">
      ${yGrid.join("")}
      ${percentAxis.join("")}
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${barBase}" y2="${barBase}" stroke="#bdc8cd" />
      ${bars.join("")}
      ${yearLabels.join("")}
      <text class="axis-text" x="${pad.left}" y="20">每股配息</text>
      <text class="axis-text" x="${width - pad.right - 28}" y="20">占比</text>
    </svg>
    <div id="compositionTooltip" class="composition-tooltip"></div>
  `;
  bindDividendCompositionTooltip(chart);
}

function drawDividendCompositionChart(rows) {
  const chart = $("dividendCompositionChart");
  if (!chart) return;
  const chronological = [...rows].sort((a, b) => String(a.exDate).localeCompare(String(b.exDate)));
  if (!chronological.length) {
    chart.innerHTML = "<div class='empty'>尚無配息組成資料</div>";
    return;
  }

  const grouped = groupRowsByYear(chronological);
  const barW = Math.max(18, Math.min(34, 360 / Math.max(chronological.length, 1)));
  const quarterGap = barW + 12;
  const yearGap = 72;
  const pad = { top: 30, right: 72, bottom: 58, left: 58 };
  const plotH = 344;
  const height = pad.top + plotH + pad.bottom;
  const maxDividend = Math.max(...chronological.map((row) => row.perShare), 1);
  const yearlyTotals = calcAnnualPerShareTotals(chronological);

  let cursor = 0;
  const localPositions = new Map();
  const yearCenters = [];
  Array.from(grouped.entries()).forEach(([year, yearRows], yearIndex) => {
    const start = cursor;
    yearRows.forEach((row, index) => {
      localPositions.set(row.exDate, cursor + index * quarterGap);
    });
    const end = cursor + Math.max(yearRows.length - 1, 0) * quarterGap;
    yearCenters.push({ year, x: (start + end) / 2 });
    cursor = end + barW + yearGap;
    if (yearIndex === grouped.size - 1) cursor = end + barW;
  });

  const viewportWidth = chart.clientWidth || 1120;
  const plotAvailable = viewportWidth - pad.left - pad.right;
  const width = cursor <= plotAvailable ? viewportWidth : pad.left + cursor + pad.right;
  const centerOffset = cursor <= plotAvailable ? (plotAvailable - cursor) / 2 : 0;
  const xFor = (row) => pad.left + centerOffset + localPositions.get(row.exDate);
  const barBase = pad.top + plotH;
  const yDividend = (value) => scale(value, 0, maxDividend * 1.15, barBase, pad.top);

  const yGrid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = maxDividend * 1.15 * ratio;
    const yy = yDividend(value);
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="16" y="${yy + 4}">${value.toFixed(2)}</text>
    `;
  });
  const percentAxis = [0, 25, 50, 75, 100].map((pct) => {
    const yy = scale(pct, 0, 100, barBase, pad.top);
    return `<text class="axis-text" x="${width - pad.right + 18}" y="${yy + 4}">${pct}%</text>`;
  });

  const bars = chronological.map((row) => {
    const xx = xFor(row) - barW / 2;
    const totalH = Math.max(4, barBase - yDividend(row.perShare));
    const incomeH = totalH * row.dividendIncomePct / 100;
    const equalizationH = totalH * row.equalizationPct / 100;
    const capitalH = totalH * row.capitalGainPct / 100;
    let top = barBase;
    const segments = [
      { h: incomeH, color: "#1f8f5f" },
      { h: equalizationH, color: "#d99b2b" },
      { h: capitalH, color: "#6f63c6" },
    ].map((seg) => {
      top -= seg.h;
      return `<rect x="${xx}" y="${top}" width="${barW}" height="${Math.max(0, seg.h)}" fill="${seg.color}" />`;
    }).join("");
    const payload = encodeURIComponent(JSON.stringify({ ...row, annualPerShare: yearlyTotals.get(row.year) || 0 }));
    return `
      <g>
        ${segments}
        <rect class="composition-hover" data-row="${payload}" x="${xx - 8}" y="${pad.top}" width="${barW + 16}" height="${plotH}" />
      </g>
    `;
  });

  const yearLabels = yearCenters.map(({ year, x }) =>
    `<text class="axis-text year-label" text-anchor="middle" x="${pad.left + centerOffset + x}" y="${height - 22}">${year}</text>`
  );

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="00919 每季配息組成直條圖">
      ${yGrid.join("")}
      ${percentAxis.join("")}
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${barBase}" y2="${barBase}" stroke="#bdc8cd" />
      ${bars.join("")}
      ${yearLabels.join("")}
      <text class="axis-text" x="${pad.left}" y="20">每股配息</text>
      <text class="axis-text" x="${width - pad.right - 28}" y="20">占比</text>
    </svg>
    <div id="compositionTooltip" class="composition-tooltip"></div>
  `;
  bindDividendCompositionTooltip(chart);
}

function drawDividendCompositionChart(rows) {
  const chart = $("dividendCompositionChart");
  if (!chart) return;
  const chronological = [...rows].sort((a, b) => String(a.exDate).localeCompare(String(b.exDate)));
  if (!chronological.length) {
    chart.innerHTML = "<div class='empty'>尚無配息組成資料</div>";
    return;
  }

  const grouped = groupRowsByYear(chronological);
  const barW = Math.max(18, Math.min(34, 360 / Math.max(chronological.length, 1)));
  const quarterGap = barW + 16;
  const yearGap = 76;
  const pad = { top: 30, right: 72, bottom: 58, left: 58 };
  const plotH = 344;
  const height = pad.top + plotH + pad.bottom;
  const maxDividend = Math.max(...chronological.map((row) => row.perShare), 1);
  const yearlyTotals = calcAnnualPerShareTotals(chronological);

  let cursor = pad.left;
  const positions = new Map();
  const yearCenters = [];
  Array.from(grouped.entries()).forEach(([year, yearRows], yearIndex) => {
    const start = cursor;
    yearRows.forEach((row, index) => {
      positions.set(row.exDate, cursor + index * quarterGap);
    });
    const end = cursor + Math.max(yearRows.length - 1, 0) * quarterGap;
    yearCenters.push({ year, x: (start + end) / 2 });
    cursor = end + yearGap;
    if (yearIndex === grouped.size - 1) cursor = end + barW + pad.right;
  });
  const width = Math.max(chart.clientWidth || 1120, cursor);
  const barBase = pad.top + plotH;
  const yDividend = (value) => scale(value, 0, maxDividend * 1.15, barBase, pad.top);

  const yGrid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = maxDividend * 1.15 * ratio;
    const yy = yDividend(value);
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="16" y="${yy + 4}">${value.toFixed(2)}</text>
    `;
  });
  const percentAxis = [0, 25, 50, 75, 100].map((pct) => {
    const yy = scale(pct, 0, 100, barBase, pad.top);
    return `<text class="axis-text" x="${width - pad.right + 18}" y="${yy + 4}">${pct}%</text>`;
  });

  const bars = chronological.map((row) => {
    const xx = positions.get(row.exDate) - barW / 2;
    const totalH = Math.max(4, barBase - yDividend(row.perShare));
    const incomeH = totalH * row.dividendIncomePct / 100;
    const equalizationH = totalH * row.equalizationPct / 100;
    const capitalH = totalH * row.capitalGainPct / 100;
    let top = barBase;
    const segments = [
      { h: incomeH, color: "#1f8f5f" },
      { h: equalizationH, color: "#d99b2b" },
      { h: capitalH, color: "#6f63c6" },
    ].map((seg) => {
      top -= seg.h;
      return `<rect x="${xx}" y="${top}" width="${barW}" height="${Math.max(0, seg.h)}" fill="${seg.color}" />`;
    }).join("");
    const payload = encodeURIComponent(JSON.stringify({ ...row, annualPerShare: yearlyTotals.get(row.year) || 0 }));
    return `
      <g>
        ${segments}
        <rect class="composition-hover" data-row="${payload}" x="${xx - 8}" y="${pad.top}" width="${barW + 16}" height="${plotH}" />
      </g>
    `;
  });

  const yearLabels = yearCenters.map(({ year, x }) =>
    `<text class="axis-text year-label" text-anchor="middle" x="${x}" y="${height - 22}">${year}</text>`
  );

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="00919 每季配息組成直條圖">
      ${yGrid.join("")}
      ${percentAxis.join("")}
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${barBase}" y2="${barBase}" stroke="#bdc8cd" />
      ${bars.join("")}
      ${yearLabels.join("")}
      <text class="axis-text" x="${pad.left}" y="20">每股配息</text>
      <text class="axis-text" x="${width - pad.right - 28}" y="20">占比</text>
    </svg>
    <div id="compositionTooltip" class="composition-tooltip"></div>
  `;
  bindDividendCompositionTooltip(chart);
}

function renderDividendEstimateTable(rows) {
  const table = document.querySelector(".dividend-table");
  if (!table) return;
  const displayRows = buildDividendEstimateRows(rows);
  table.innerHTML = `
    <thead>
      <tr>
        <th>除息日 / 年度</th>
        <th>發放日</th>
        <th>當時股數</th>
        <th>配息估算</th>
        <th>54C 估算</th>
        <th>補充保費</th>
        <th>年度配息統計</th>
      </tr>
    </thead>
    <tbody id="dividendTableBody">
      ${displayRows.map((item) => {
        if (item.type === "annual") {
          return `
            <tr class="annual-summary-row">
              <td>${item.year}</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td>${item.year} 每股 ${fmt.money(item.perShareTotal, 2)} 元，共 ${item.count} 次</td>
            </tr>
          `;
        }
        const row = item.row;
        const healthText = row.healthPremium > 0
          ? `<span class="dividend-risk">$${fmt.money(row.healthPremium)}</span>`
          : `<span class="dividend-ok">未達</span>`;
        return `
          <tr>
            <td>${row.exDate || "--"}</td>
            <td>${row.payDate || "--"}</td>
            <td>${fmt.money(row.shares)} 股</td>
            <td>$${fmt.money(row.cash)}</td>
            <td>$${fmt.money(row.estimated54c)}</td>
            <td>${healthText}</td>
            <td>${item.showAnnual ? `${row.year} 每股 ${fmt.money(item.perShareTotal, 2)} 元，共 ${item.count} 次` : ""}</td>
          </tr>
        `;
      }).join("")}
    </tbody>
  `;
}

function buildDividendEstimateRows(rows) {
  return Array.from(groupRowsByYear(rows).entries())
    .sort(([yearA], [yearB]) => String(yearB).localeCompare(String(yearA)))
    .flatMap(([year, yearRows]) => {
      const sorted = [...yearRows].sort((a, b) => String(b.exDate).localeCompare(String(a.exDate)));
      const perShareTotal = sorted.reduce((sum, row) => sum + row.perShare, 0);
      const hasTracked = sorted.some((row) => row.isTracked);
      if (!hasTracked) {
        return [{ type: "annual", year, perShareTotal, count: sorted.length }];
      }
      return sorted
        .filter((row) => row.isTracked)
        .map((row, index) => ({
          type: "quarter",
          row,
          showAnnual: index === 0,
          perShareTotal,
          count: sorted.length,
        }));
    });
}
