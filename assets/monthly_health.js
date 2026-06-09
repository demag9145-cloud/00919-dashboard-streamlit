const MONTHLY_SIGNAL_RULES = {
  note: "首頁總燈號是唯一總判斷；每日、每月、每季、持股、每年只提供模組燈號與原因。",
  merge: "任一模組紅燈則首頁紅燈；無紅燈但任一模組黃燈則首頁黃燈；其餘為綠燈。",
};

const baseRenderForMonthly = render;
render = function renderWithMonthlyHealth() {
  baseRenderForMonthly();
  renderMonthlyHealth();
};

function getMonthlyAum100mValue(row) {
  if (!row) return NaN;
  // Monthly health uses only true month-end AUM.  Latest snapshots from
  // Capital Fund / TWSE must not be drawn as monthly bars.
  if (row.aum_is_current_snapshot || row.monthly_aum_status === "pending" || row.aum_pending) return NaN;
  const direct = Number(row.aum_100m_twd);
  if (Number.isFinite(direct) && direct > 0) return direct;
  const million = Number(row.aum_million_twd);
  if (!Number.isFinite(million) || million <= 0) return NaN;
  return million < 20000 ? million : million / 100;
}


function getSafeBeneficiaryCount(row) {
  const raw = Number(row?.beneficiary_count);
  if (!Number.isFinite(raw) || raw <= 0) return NaN;
  if (raw >= 100000 && raw <= 5000000) return Math.round(raw);
  const dividedBy10 = raw / 10;
  if (raw > 5000000 && dividedBy10 >= 100000 && dividedBy10 <= 5000000) return Math.round(dividedBy10);
  return NaN;
}

function enrichMonthlyEtfRows(rows) {
  const enriched = rows.map((row) => ({
    ...row,
    _beneficiary_count_safe: getSafeBeneficiaryCount(row),
    _aum_100m_safe: getMonthlyAum100mValue(row),
  }));
  enriched.forEach((row, index) => {
    const previous = enriched[index - 1];
    const currentCount = row._beneficiary_count_safe;
    const previousCount = previous?._beneficiary_count_safe;
    if (Number.isFinite(currentCount) && Number.isFinite(previousCount) && previousCount > 0) {
      row._beneficiary_change_pct_safe = ((currentCount - previousCount) / previousCount) * 100;
    } else if (Number.isFinite(Number(row.beneficiary_change_pct))) {
      row._beneficiary_change_pct_safe = Number(row.beneficiary_change_pct);
    }
  });
  return enriched;
}

function getPaddedDomain(values, minPaddingRatio = 0.08) {
  const clean = values.filter((value) => Number.isFinite(value));
  if (!clean.length) return [0, 1];
  const rawMin = Math.min(...clean);
  const rawMax = Math.max(...clean);
  const span = Math.max(rawMax - rawMin, Math.abs(rawMax || 1) * minPaddingRatio, 1);
  const pad = span * 0.18;
  return [Math.max(0, rawMin - pad), rawMax + pad];
}

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

  // 這張圖用「相對投入成本」顯示，避免投入本金 / 市值 / 含息總值太接近時折線重疊。
  const displayRows = rows.map((row) => ({
    ...row,
    costBase: 0,
    marketReturnValue: row.marketValue - row.cost,
    totalReturnValue: row.totalValue - row.cost,
  }));

  const width = Math.max(980, displayRows.length * 64 + 170);
  const height = 380;
  const pad = { top: 34, right: 42, bottom: 54, left: 82 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const values = displayRows.flatMap((row) => [row.costBase, row.marketReturnValue, row.totalReturnValue]);
  const clean = values.filter((value) => Number.isFinite(value));
  const rawMin = clean.length ? Math.min(...clean) : 0;
  const rawMax = clean.length ? Math.max(...clean) : 1;
  const rawSpan = Math.max(rawMax - rawMin, Math.abs(rawMax || rawMin || 1) * 0.18, 1000);
  let minValue = rawMin - rawSpan * 0.18;
  let maxValue = rawMax + rawSpan * 0.22;
  if (rawMin >= 0) minValue = Math.min(0, minValue);
  if (rawMax <= 0) maxValue = Math.max(0, maxValue);

  const x = (_, index) => pad.left + (index / Math.max(displayRows.length - 1, 1)) * plotW;
  const y = (value) => scale(value, minValue, maxValue, pad.top + plotH, pad.top);
  const path = (key) => displayRows.map((row, index) => `${index ? "L" : "M"} ${x(row, index)} ${y(row[key])}`).join(" ");
  const zeroY = y(0);
  const grid = [0, 1, 2, 3, 4].map((i) => {
    const yy = pad.top + (plotH / 4) * i;
    const value = maxValue - ((maxValue - minValue) / 4) * i;
    const label = value < 0 ? `-$${fmt.money(Math.abs(value))}` : `$${fmt.money(value)}`;
    return `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" /><text class="axis-text" x="12" y="${yy + 4}">${label}</text>`;
  });
  const labelStep = displayRows.length > 30 ? 4 : displayRows.length > 18 ? 3 : displayRows.length > 10 ? 2 : 1;
  const labels = displayRows.map((row, index) => {
    const show = index === 0 || index === displayRows.length - 1 || index % labelStep === 0;
    return show ? `<text class="axis-text" text-anchor="middle" x="${x(row, index)}" y="${height - 22}">${row.month.slice(2)}</text>` : "";
  });
  const zones = displayRows.map((row, index) => {
    const zoneW = plotW / Math.max(displayRows.length - 1, 1);
    const xx = Math.max(pad.left, x(row, index) - zoneW / 2);
    const widthValue = index === 0 || index === displayRows.length - 1 ? zoneW / 2 : zoneW;
    const payload = encodeURIComponent(JSON.stringify(row));
    return `<rect class="monthly-hover-zone" data-row="${payload}" data-x="${x(row, index).toFixed(2)}" x="${xx.toFixed(2)}" y="${pad.top}" width="${widthValue.toFixed(2)}" height="${plotH}" />`;
  });
  const points = displayRows.map((row, index) => `
    <circle class="chart-point monthly-chart-point" cx="${x(row, index)}" cy="${y(row.costBase)}" r="4.2" fill="#172124" />
    <circle class="chart-point monthly-chart-point" cx="${x(row, index)}" cy="${y(row.marketReturnValue)}" r="5" fill="#1f5fbf" />
    <circle class="chart-point monthly-chart-point" cx="${x(row, index)}" cy="${y(row.totalReturnValue)}" r="5" fill="#198754" />
  `).join("");

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" style="width:${width}px; max-width:none;" role="img" aria-label="每月含息報酬相對投入成本折線圖">
      ${grid.join("")}
      <line class="grid-line zero-line" x1="${pad.left}" x2="${width - pad.right}" y1="${zeroY}" y2="${zeroY}" stroke-dasharray="6 5" />
      <line id="monthlyReturnGuide" class="hover-guide" x1="${pad.left}" x2="${pad.left}" y1="${pad.top}" y2="${pad.top + plotH}" />
      <text class="axis-text chart-note" x="${pad.left}" y="20">相對投入成本顯示，避免絕對金額過近時線條重疊</text>
      <path d="${path("costBase")}" fill="none" stroke="#172124" stroke-width="2.5" stroke-dasharray="7 5" />
      <path d="${path("marketReturnValue")}" fill="none" stroke="#1f5fbf" stroke-width="3.5" />
      <path d="${path("totalReturnValue")}" fill="none" stroke="#198754" stroke-width="3.5" />
      ${points}
      ${labels.join("")}
      ${zones.join("")}
    </svg>
    <div id="monthlyReturnTooltip" class="chart-tooltip monthly-chart-tooltip"></div>
  `;
  bindMonthlyReturnTooltip(chart);
}



function bindMonthlyReturnTooltip(chart) {
  const tooltip = chart.querySelector("#monthlyReturnTooltip");
  const guide = chart.querySelector("#monthlyReturnGuide");
  if (!tooltip) return;
  chart.querySelectorAll(".monthly-hover-zone").forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      const row = JSON.parse(decodeURIComponent(zone.dataset.row));
      tooltip.innerHTML = `
        <strong>${row.month}</strong>
        <div><span>持有股數</span><b>${fmt.money(Number(row.shares))} 股</b></div>
        <div><span>投入成本</span><b>$${fmt.money(Number(row.cost))}</b></div>
        <div><span>月底市值</span><b>$${fmt.money(Number(row.marketValue))}</b></div>
        <div><span>累積配息</span><b>$${fmt.money(Number(row.cumulativeDividend))}</b></div>
        <div><span>含息總值</span><b>$${fmt.money(Number(row.totalValue))}</b></div>
        <div><span>含息損益</span><b>$${fmt.money(Number(row.totalReturn))}</b></div>
        <div><span>含息報酬率</span><b>${fmt.pct(Number(row.totalReturnPct))}</b></div>
      `;
      tooltip.classList.add("show");
      if (guide) {
        guide.classList.add("active");
        guide.setAttribute("x1", zone.dataset.x);
        guide.setAttribute("x2", zone.dataset.x);
      }
    });
    zone.addEventListener("mousemove", (event) => {
      const box = chart.getBoundingClientRect();
      const left = Math.min(event.clientX - box.left + 18 + chart.scrollLeft, chart.scrollLeft + box.width - 300);
      const top = Math.max(event.clientY - box.top - 16 + chart.scrollTop, chart.scrollTop + 10);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    });
    zone.addEventListener("mouseleave", () => {
      tooltip.classList.remove("show");
      if (guide) guide.classList.remove("active");
    });
  });
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
  const rows = enrichMonthlyEtfRows((state.data.monthly_history || state.data.monthly_size || [])
    .filter((row) => row.month && (row.aum_million_twd != null || row.aum_100m_twd != null || row.beneficiary_count != null))
    .sort((a, b) => String(a.month).localeCompare(String(b.month))));
  if (chart) drawMonthlyEtfHealthChart(chart, rows);
  const body = $("monthlyEtfTableBody");
  if (!body) return;
  body.innerHTML = rows.length
    ? [...rows].reverse().map((row, index, reversed) => {
      const newer = reversed[index - 1];
      const rowAum100m = row._aum_100m_safe;
      const newerAum100m = newer ? newer._aum_100m_safe : NaN;
      const aumChangePct = newer && Number.isFinite(rowAum100m) && rowAum100m > 0 && Number.isFinite(newerAum100m)
        ? ((newerAum100m - rowAum100m) / rowAum100m) * 100
        : null;
      const changeText = [
        Number.isFinite(row._beneficiary_change_pct_safe) ? `受益人 ${fmt.pct(row._beneficiary_change_pct_safe)}` : null,
        Number.isFinite(aumChangePct) ? `AUM ${fmt.pct(aumChangePct)}` : null,
      ].filter(Boolean).join(" / ");
      const aumPending = !Number.isFinite(rowAum100m) && row.beneficiary_count != null;
      const aumText = Number.isFinite(rowAum100m)
        ? `${fmt.money(rowAum100m)} 億${row.aum_is_current_snapshot ? "（最新）" : ""}`
        : (aumPending ? "待補" : "--");
      const detailText = [
        changeText || null,
        row.aum_pending ? "AUM 待月表補齊" : null,
      ].filter(Boolean).join(" / ");
      return `
        <tr>
          <td>${row.month}</td>
          <td class="${aumPending ? "pending" : ""}">${aumText}</td>
          <td>${Number.isFinite(row._beneficiary_count_safe) ? fmt.money(row._beneficiary_count_safe) : "--"} 人</td>
          <td>${detailText || "--"}</td>
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
  const width = Math.max(760, rows.length * 62 + 160);
  const height = 360;
  const pad = { top: 28, right: 80, bottom: 48, left: 72 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const aumValues = rows.map((row) => row._aum_100m_safe).filter((value) => Number.isFinite(value) && value > 0);
  const beneficiaryValues = rows
    .map((row) => row._beneficiary_count_safe / 10000)
    .filter((value) => Number.isFinite(value) && value > 0);
  const [minAum, maxAum] = getPaddedDomain(aumValues, 0.08);
  const [minBeneficiary, maxBeneficiary] = getPaddedDomain(beneficiaryValues, 0.08);
  const band = plotW / Math.max(rows.length, 1);
  const barW = Math.min(36, Math.max(18, band * 0.48));
  const x = (index) => pad.left + band * index + band / 2;
  const yAum = (value) => scale(value, minAum, maxAum, pad.top + plotH, pad.top);
  const yBeneficiary = (value) => scale(value, minBeneficiary, maxBeneficiary, pad.top + plotH, pad.top);
  const beneficiaryPoints = rows
    .map((row, index) => ({ index, value: row._beneficiary_count_safe / 10000 }))
    .filter((point) => Number.isFinite(point.value) && point.value > 0);
  const linePath = beneficiaryPoints.map((point, index) => {
    return `${index ? "L" : "M"} ${x(point.index)} ${yBeneficiary(point.value)}`;
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
  const rowsWithChange = rows.map((row, index) => {
    const previous = rows[index - 1];
    const aumChangePct = previous && Number.isFinite(previous._aum_100m_safe) && previous._aum_100m_safe > 0 && Number.isFinite(row._aum_100m_safe)
      ? ((row._aum_100m_safe - previous._aum_100m_safe) / previous._aum_100m_safe) * 100
      : null;
    return { ...row, _aum_change_pct_safe: aumChangePct };
  });
  const bars = rowsWithChange.map((row, index) => {
    const aum = row._aum_100m_safe;
    const beneficiaries = row._beneficiary_count_safe / 10000;
    const bar = Number.isFinite(aum) && aum > 0 ? (() => {
      const yy = yAum(aum);
      const h = Math.max(2, pad.top + plotH - yy);
      return `<rect class="aum-bar" x="${x(index) - barW / 2}" y="${yy}" width="${barW}" height="${h}" rx="4" />`;
    })() : (row.aum_pending ? `<text class="axis-text" text-anchor="middle" x="${x(index)}" y="${pad.top + plotH - 6}">待補</text>` : "");
    const point = Number.isFinite(beneficiaries) && beneficiaries > 0 ? `
      <circle class="chart-point monthly-chart-point" cx="${x(index)}" cy="${yBeneficiary(beneficiaries)}" r="5.5" fill="#c2410c" />` : "";
    return `${bar}${point}`;
  });
  const zones = rowsWithChange.map((row, index) => {
    const payload = encodeURIComponent(JSON.stringify(row));
    return `<rect class="monthly-hover-zone" data-row="${payload}" data-x="${x(index).toFixed(2)}" x="${(pad.left + band * index).toFixed(2)}" y="${pad.top}" width="${band.toFixed(2)}" height="${plotH}" />`;
  });
  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" style="width:${width}px; max-width:none;" role="img" aria-label="ETF 規模健康">
      ${grid.join("")}
      <line id="monthlyEtfGuide" class="hover-guide" x1="${pad.left}" x2="${pad.left}" y1="${pad.top}" y2="${pad.top + plotH}" />
      <text class="axis-text" x="${pad.left}" y="18">AUM</text>
      <text class="axis-text" text-anchor="end" x="${width - pad.right}" y="18">受益人數</text>
      ${bars.join("")}
      <path d="${linePath}" fill="none" stroke="#c2410c" stroke-width="3" />
      ${labels.join("")}
      ${zones.join("")}
    </svg>
    <div id="monthlyEtfTooltip" class="chart-tooltip monthly-chart-tooltip"></div>
  `;
  bindMonthlyEtfTooltip(chart);
}



function bindMonthlyEtfTooltip(chart) {
  const tooltip = chart.querySelector("#monthlyEtfTooltip");
  const guide = chart.querySelector("#monthlyEtfGuide");
  if (!tooltip) return;
  chart.querySelectorAll(".monthly-hover-zone").forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      const row = JSON.parse(decodeURIComponent(zone.dataset.row));
      const aum = Number(row._aum_100m_safe);
      const beneficiaries = Number(row._beneficiary_count_safe);
      tooltip.innerHTML = `
        <strong>${row.month}</strong>
        <div><span>AUM</span><b>${Number.isFinite(aum) ? `${fmt.money(aum)} 億` : "待補"}</b></div>
        <div><span>AUM 月增率</span><b>${Number.isFinite(Number(row._aum_change_pct_safe)) ? fmt.pct(Number(row._aum_change_pct_safe)) : "--"}</b></div>
        <div><span>受益人數</span><b>${Number.isFinite(beneficiaries) ? `${fmt.money(beneficiaries)} 人` : "--"}</b></div>
        <div><span>受益人月增率</span><b>${Number.isFinite(Number(row._beneficiary_change_pct_safe)) ? fmt.pct(Number(row._beneficiary_change_pct_safe)) : "--"}</b></div>
        <div><span>來源</span><b>${row.monthly_aum_source || row.beneficiary_source || row.source || "--"}</b></div>
      `;
      tooltip.classList.add("show");
      if (guide) {
        guide.classList.add("active");
        guide.setAttribute("x1", zone.dataset.x);
        guide.setAttribute("x2", zone.dataset.x);
      }
    });
    zone.addEventListener("mousemove", (event) => {
      const box = chart.getBoundingClientRect();
      const left = Math.min(event.clientX - box.left + 18 + chart.scrollLeft, chart.scrollLeft + box.width - 300);
      const top = Math.max(event.clientY - box.top - 16 + chart.scrollTop, chart.scrollTop + 10);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    });
    zone.addEventListener("mouseleave", () => {
      tooltip.classList.remove("show");
      if (guide) guide.classList.remove("active");
    });
  });
}

setTimeout(() => {
  if (typeof state !== "undefined" && state.data) renderMonthlyHealth();
}, 0);
