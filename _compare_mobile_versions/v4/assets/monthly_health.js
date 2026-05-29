const MONTHLY_SIGNAL_RULES = {
  note: "首頁總燈號是唯一總判斷；每日、每月、每季、持股、每年只提供模組燈號與原因。",
  merge: "任一模組紅燈則首頁紅燈；無紅燈但任一模組黃燈則首頁黃燈；其餘為綠燈。",
};

const baseRenderForMonthly = render;
render = function renderWithMonthlyHealth() {
  baseRenderForMonthly();
  renderMonthlyHealth();
};

function renderMonthlyHealth() {
  if (!state?.data) return;
  const rows = calcMonthlyReturnRows(
    state.data.monthly_history || [],
    state.data.daily || [],
    state.trades || [],
    state.data.dividends || []
  );
  const signal = calcMonthlySignal(rows);
  renderMonthlySignal(signal);
  drawMonthlyReturnChart(rows);
  renderMonthlyReturnTable(rows);
  renderMonthlyEtfHealth();
}

function calcMonthlyReturnRows(monthlyHistoryRows, dailyRows, trades, dividends) {
  const sortedTrades = [...trades].sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date)));
  const firstTradeDate = sortedTrades.find((trade) => trade.trade_date)?.trade_date;
  if (!firstTradeDate) return [];

  const monthlyPriceRows = getMonthlyPriceRows(monthlyHistoryRows, dailyRows)
    .filter((row) => row.date >= firstTradeDate)
    .sort((a, b) => a.date.localeCompare(b.date));

  return monthlyPriceRows.map((daily) => {
    const position = calcPositionUntilDate(sortedTrades, daily.date);
    const cumulativeDividend = dividends.reduce((sum, dividend) => {
      if (!dividend.ex_date || dividend.ex_date > daily.date) return sum;
      const shares = calcSharesOnDate(sortedTrades, dividend.ex_date);
      return sum + shares * Number(dividend.dividend_per_share || 0);
    }, 0);
    const marketPrice = Number(daily.market_price || 0);
    const marketValue = position.holdingShares * marketPrice;
    const totalValue = marketValue + cumulativeDividend + position.realizedPnl;
    const totalReturn = totalValue - position.totalCost;
    const totalReturnPct = position.totalCost ? (totalReturn / position.totalCost) * 100 : 0;
    return {
      month: daily.date.slice(0, 7),
      date: daily.date,
      shares: position.holdingShares,
      cost: position.totalCost,
      marketValue,
      cumulativeDividend,
      totalValue,
      totalReturn,
      totalReturnPct,
    };
  });
}

function getMonthlyPriceRows(monthlyHistoryRows, dailyRows) {
  const historyRows = (monthlyHistoryRows || [])
    .filter((row) => row.month && Number.isFinite(Number(row.avg_market_price)))
    .map((row) => ({
      month: row.month,
      date: row.month_end_date || `${row.month}-28`,
      market_price: Number(row.avg_market_price),
    }));
  if (historyRows.length) return historyRows;

  return Array.from(
    dailyRows
      .filter((row) => row.date && Number.isFinite(Number(row.market_price)))
      .reduce((map, row) => {
        const key = row.date.slice(0, 7);
        const current = map.get(key) || { month: key, date: row.date, marketPriceSum: 0, count: 0 };
        current.date = row.date > current.date ? row.date : current.date;
        current.marketPriceSum += Number(row.market_price);
        current.count += 1;
        current.market_price = current.marketPriceSum / current.count;
        map.set(key, current);
        return map;
      }, new Map())
      .values()
  );
}

function calcPositionUntilDate(sortedTrades, date) {
  let holdingShares = 0;
  let totalCost = 0;
  let realizedPnl = 0;
  sortedTrades
    .filter((trade) => trade.trade_date <= date)
    .forEach((trade) => {
      const shares = Number(trade.shares || 0);
      const price = Number(trade.price || 0);
      if (trade.action === "sell") {
        const avgCost = holdingShares ? totalCost / holdingShares : 0;
        const costBasis = avgCost * shares;
        holdingShares -= shares;
        totalCost -= costBasis;
        realizedPnl += shares * price - costBasis;
      } else {
        holdingShares += shares;
        totalCost += shares * price;
      }
    });
  return { holdingShares, totalCost, realizedPnl };
}

function calcMonthlySignal(rows) {
  const settings = typeof window.getSignalSettings === "function"
    ? window.getSignalSettings()
    : { monthlyReturnRedPct: 0, beneficiaryDeclineMonths: 3 };
  const returnRedPct = Number(settings.monthlyReturnRedPct ?? 0);
  const declineMonths = Math.max(1, Math.round(Number(settings.beneficiaryDeclineMonths ?? 3)));
  const latest = rows[rows.length - 1];
  if (!latest) {
    return { level: "unknown", label: "每月燈號：資料不足", reason: "尚無可用的月度含息報酬資料。" };
  }
  if (latest.totalReturnPct < returnRedPct) {
    return {
      level: "red",
      label: "每月燈號：紅燈",
      reason: `含息報酬率 ${fmt.pct(latest.totalReturnPct)} 低於紅燈門檻 ${fmt.pct(returnRedPct)}，需要檢查價格與配息是否拖累報酬。`,
    };
  }
  const previous = rows[rows.length - 2];
  if (previous && latest.totalReturn < previous.totalReturn) {
    return {
      level: "yellow",
      label: "每月燈號：黃燈",
      reason: "含息損益仍為正，但較上月下降，先列入觀察。",
    };
  }
  const sizeRows = (state.data.monthly_size || []).filter((row) => Number.isFinite(Number(row.beneficiary_change_pct)));
  const latestSizeRows = sizeRows.slice(-declineMonths);
  if (latestSizeRows.length >= declineMonths && latestSizeRows.every((row) => Number(row.beneficiary_change_pct) < 0)) {
    return {
      level: "yellow",
      label: "每月燈號：黃燈",
      reason: `含息報酬仍為正，但受益人數已連續 ${declineMonths} 個月下降，ETF 規模面需要觀察。`,
    };
  }
  return {
    level: "green",
    label: "每月燈號：綠燈",
    reason: "含息報酬為正，月度追蹤狀態正常；ETF 規模資料已納入輔助判斷。",
  };
}

function renderMonthlySignal(signal) {
  const light = $("monthlySignalLight");
  if (light) light.className = `mini-signal-light ${signal.level || "yellow"}`;
  setText("monthlySignalLabel", signal.label);
  setText("monthlySignalReason", signal.reason);
}

function drawMonthlyReturnChart(rows) {
  const chart = $("monthlyReturnChart");
  if (!chart) return;
  if (!rows.length) {
    chart.innerHTML = "<div class='empty'>尚無月度含息報酬資料</div>";
    return;
  }
  const width = Math.max(980, rows.length * 46 + 140);
  const height = 360;
  const pad = { top: 26, right: 32, bottom: 48, left: 70 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const values = rows.flatMap((row) => [row.cost, row.marketValue, row.totalValue]);
  const minValue = Math.min(0, ...values) * 0.98;
  const maxValue = Math.max(...values, 1) * 1.08;
  const x = (_, index) => pad.left + (index / Math.max(rows.length - 1, 1)) * plotW;
  const y = (value) => scale(value, minValue, maxValue, pad.top + plotH, pad.top);
  const path = (key) => rows.map((row, index) => `${index ? "L" : "M"} ${x(row, index)} ${y(row[key])}`).join(" ");
  const grid = [0, 1, 2, 3, 4].map((i) => {
    const yy = pad.top + (plotH / 4) * i;
    const value = maxValue - ((maxValue - minValue) / 4) * i;
    return `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" /><text class="axis-text" x="12" y="${yy + 4}">$${fmt.money(value)}</text>`;
  });
  const labelStep = rows.length > 30 ? 4 : rows.length > 18 ? 3 : rows.length > 10 ? 2 : 1;
  const labels = rows.map((row, index) => {
    const show = index === 0 || index === rows.length - 1 || index % labelStep === 0;
    return show ? `<text class="axis-text" text-anchor="middle" x="${x(row, index)}" y="${height - 20}">${row.month.slice(2)}</text>` : "";
  });
  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" style="width:${width}px; max-width:none;" role="img" aria-label="每月含息報酬折線圖">
      ${grid.join("")}
      <path d="${path("cost")}" fill="none" stroke="#172124" stroke-width="2.5" />
      <path d="${path("marketValue")}" fill="none" stroke="#1f5fbf" stroke-width="3" />
      <path d="${path("totalValue")}" fill="none" stroke="#198754" stroke-width="3" />
      ${rows.map((row, index) => `
        <circle cx="${x(row, index)}" cy="${y(row.cost)}" r="3" fill="#172124" />
        <circle cx="${x(row, index)}" cy="${y(row.marketValue)}" r="3" fill="#1f5fbf" />
        <circle cx="${x(row, index)}" cy="${y(row.totalValue)}" r="3" fill="#198754" />
      `).join("")}
      ${labels.join("")}
    </svg>
  `;
}

function renderMonthlyReturnTable(rows) {
  const body = $("monthlyReturnTableBody");
  if (!body) return;
  body.innerHTML = rows.length
    ? [...rows].reverse().map((row) => `
      <tr>
        <td>${row.month}</td>
        <td>${fmt.money(row.shares)} 股</td>
        <td>$${fmt.money(row.cost)}</td>
        <td>$${fmt.money(row.marketValue)}</td>
        <td>$${fmt.money(row.cumulativeDividend)}</td>
        <td>$${fmt.money(row.totalValue)}</td>
        <td class="${row.totalReturn >= 0 ? "positive" : "negative"}">$${fmt.money(row.totalReturn)}</td>
        <td class="${row.totalReturnPct >= 0 ? "positive" : "negative"}">${fmt.pct(row.totalReturnPct)}</td>
      </tr>
    `).join("")
    : "<tr><td colspan='8'>尚無月度資料</td></tr>";
}

function renderMonthlyEtfHealth() {
  const chart = $("monthlyEtfHealthChart");
  const rows = (state.data.monthly_history || state.data.monthly_size || [])
    .filter((row) => row.month && (row.aum_million_twd != null || row.aum_100m_twd != null || row.beneficiary_count != null))
    .sort((a, b) => String(a.month).localeCompare(String(b.month)));
  if (chart) drawMonthlyEtfHealthChart(chart, rows);
  const body = $("monthlyEtfTableBody");
  if (!body) return;
  body.innerHTML = rows.length
    ? [...rows].reverse().map((row, index, reversed) => {
      const newer = reversed[index - 1];
      const rowAum = Number(row.aum_million_twd || Number(row.aum_100m_twd) * 100);
      const newerAum = newer ? Number(newer.aum_million_twd || Number(newer.aum_100m_twd) * 100) : null;
      const aumChangePct = newer && rowAum
        ? ((newerAum - rowAum) / rowAum) * 100
        : null;
      const changeText = [
        Number.isFinite(Number(row.beneficiary_change_pct)) ? `受益人 ${fmt.pct(row.beneficiary_change_pct)}` : null,
        Number.isFinite(aumChangePct) ? `AUM ${fmt.pct(aumChangePct)}` : null,
      ].filter(Boolean).join(" / ");
      return `
        <tr>
          <td>${row.month}</td>
          <td>${fmt.money(rowAum / 100)} 億</td>
          <td>${fmt.money(row.beneficiary_count)} 人</td>
          <td>${changeText || "--"}</td>
        </tr>
      `;
    }).join("")
    : "<tr><td colspan='4'>尚未抓到 AUM / 受益人數資料。</td></tr>";
}

function drawMonthlyEtfHealthChart(chart, rows) {
  if (!rows.length) {
    chart.innerHTML = "<div class='empty'>尚未抓到 AUM / 受益人數資料。</div>";
    return;
  }
  chart.classList.remove("etf-health-empty");
  const width = Math.max(760, rows.length * 58 + 150);
  const height = 360;
  const pad = { top: 28, right: 76, bottom: 48, left: 70 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const aumValues = rows.map((row) => Number(row.aum_million_twd || Number(row.aum_100m_twd) * 100) / 100);
  const beneficiaryValues = rows.map((row) => Number(row.beneficiary_count || 0) / 10000);
  const minAum = Math.min(...aumValues) * 0.96;
  const maxAum = Math.max(...aumValues) * 1.04;
  const minBeneficiary = Math.min(...beneficiaryValues) * 0.96;
  const maxBeneficiary = Math.max(...beneficiaryValues) * 1.04;
  const band = plotW / Math.max(rows.length, 1);
  const barW = Math.min(34, Math.max(16, band * 0.48));
  const x = (index) => pad.left + band * index + band / 2;
  const yAum = (value) => scale(value, minAum, maxAum, pad.top + plotH, pad.top);
  const yBeneficiary = (value) => scale(value, minBeneficiary, maxBeneficiary, pad.top + plotH, pad.top);
  const linePath = rows.map((row, index) => {
    const value = Number(row.beneficiary_count || 0) / 10000;
    return `${index ? "L" : "M"} ${x(index)} ${yBeneficiary(value)}`;
  }).join(" ");
  const grid = [0, 1, 2, 3, 4].map((i) => {
    const yy = pad.top + (plotH / 4) * i;
    const aum = maxAum - ((maxAum - minAum) / 4) * i;
    const beneficiaries = maxBeneficiary - ((maxBeneficiary - minBeneficiary) / 4) * i;
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="12" y="${yy + 4}">${fmt.money(aum)} 億</text>
      <text class="axis-text" text-anchor="end" x="${width - 12}" y="${yy + 4}">${fmt.money(beneficiaries)} 萬</text>
    `;
  });
  const labels = rows.map((row, index) => {
    const show = rows.length <= 8 || index % 2 === 0 || index === rows.length - 1;
    return show ? `<text class="axis-text" text-anchor="middle" x="${x(index)}" y="${height - 20}">${row.month.slice(5)}</text>` : "";
  });
  const bars = rows.map((row, index) => {
    const aum = Number(row.aum_million_twd || Number(row.aum_100m_twd) * 100) / 100;
    const y = yAum(aum);
    const h = pad.top + plotH - y;
    const beneficiaries = Number(row.beneficiary_count || 0) / 10000;
    return `
      <rect class="aum-bar" x="${x(index) - barW / 2}" y="${y}" width="${barW}" height="${h}" rx="4">
        <title>${row.month}
AUM：${fmt.money(aum)} 億
受益人數：${fmt.money(row.beneficiary_count)} 人
受益人月增率：${fmt.pct(row.beneficiary_change_pct)}</title>
      </rect>
      <circle cx="${x(index)}" cy="${yBeneficiary(beneficiaries)}" r="3.5" fill="#c2410c">
        <title>${row.month} 受益人數：${fmt.money(row.beneficiary_count)} 人</title>
      </circle>
    `;
  });
  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" style="width:${width}px; max-width:none;" role="img" aria-label="ETF 規模健康">
      ${grid.join("")}
      <text class="axis-text" x="${pad.left}" y="18">AUM</text>
      <text class="axis-text" text-anchor="end" x="${width - pad.right}" y="18">受益人數</text>
      ${bars.join("")}
      <path d="${linePath}" fill="none" stroke="#c2410c" stroke-width="3" />
      ${labels.join("")}
    </svg>
  `;
}

setTimeout(() => {
  if (typeof state !== "undefined" && state.data) renderMonthlyHealth();
}, 0);
