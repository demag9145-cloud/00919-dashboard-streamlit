function dividendNum(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function dividendHasCompositionRaw(dividend) {
  if (!dividend) return false;
  if (dividend.composition_status === "complete") return true;
  return [
    dividend.dividend_income_pct,
    dividend.interest_income_pct,
    dividend.equalization_pct,
    dividend.capital_gain_pct,
    dividend.other_income_pct,
  ].some((value) => value !== null && value !== undefined && value !== "");
}

function dividendStatusText(row) {
  if (!row) return "--";
  if (row.hasComposition) return "complete";
  if (row.perShare > 0) return "pending：已取得配息，54C 組成待補";
  return "pending";
}

function dividendSourceText(row) {
  if (!row) return "--";
  const eventSource = row.eventSource || row.source || "未標示";
  const compositionSource = row.compositionSource || (row.hasComposition ? eventSource : "待 TWSE / 官方補齊");
  return `事件：${eventSource}；組成：${compositionSource}`;
}

calcDividendRows = function calcDividendRows(dividends, trades) {
  const sortedTrades = [...(trades || [])].sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date)));
  const trackStartDate = sortedTrades[0]?.trade_date || "";
  const premiumThreshold = typeof HEALTH_PREMIUM_THRESHOLD !== "undefined" ? HEALTH_PREMIUM_THRESHOLD : 20000;
  const premiumRate = typeof HEALTH_PREMIUM_RATE !== "undefined" ? HEALTH_PREMIUM_RATE : 0.0211;

  return [...(dividends || [])]
    .filter((dividend) => dividend && dividend.ex_date)
    .sort((a, b) => String(b.ex_date).localeCompare(String(a.ex_date)))
    .map((dividend) => {
      const exDate = dividend.ex_date || "";
      const isTracked = Boolean(trackStartDate && exDate >= trackStartDate);
      const shares = isTracked ? calcSharesOnDate(sortedTrades, exDate) : 0;
      const perShare = dividendNum(dividend.dividend_per_share, 0);
      const hasComposition = dividendHasCompositionRaw(dividend);
      const dividendIncomePct = hasComposition ? dividendNum(dividend.dividend_income_pct, 0) : 0;
      const equalizationPct = hasComposition ? dividendNum(dividend.equalization_pct, 0) : 0;
      const capitalGainPct = hasComposition ? dividendNum(dividend.capital_gain_pct, 0) : 0;
      const interestIncomePct = hasComposition ? dividendNum(dividend.interest_income_pct, 0) : 0;
      const otherIncomePctRaw = hasComposition ? dividendNum(dividend.other_income_pct, NaN) : 100;
      const otherPct = hasComposition
        ? (Number.isFinite(otherIncomePctRaw)
            ? otherIncomePctRaw
            : Math.max(0, 100 - dividendIncomePct - equalizationPct - capitalGainPct - interestIncomePct))
        : 100;
      const estimated54cPerShare = hasComposition
        ? dividendNum(dividend.estimated_54c_per_share, perShare * dividendIncomePct / 100)
        : null;
      const estimated54c = isTracked && estimated54cPerShare !== null ? shares * estimated54cPerShare : null;
      const healthPremium = estimated54c !== null && estimated54c >= premiumThreshold ? estimated54c * premiumRate : 0;
      return {
        exDate,
        payDate: dividend.pay_date || "",
        recordDate: dividend.record_date || "",
        baseDate: dividend.base_date || dividend.valuation_date || "",
        year: exDate.slice(0, 4) || "----",
        perShare,
        dividendIncomePct,
        interestIncomePct,
        equalizationPct,
        capitalGainPct,
        otherPct,
        hasComposition,
        compositionStatus: hasComposition ? "complete" : "pending",
        isTracked,
        shares,
        cash: shares * perShare,
        estimated54c,
        estimated54cPerShare,
        healthPremium,
        eventSource: dividend.event_source || dividend.source || "",
        compositionSource: dividend.composition_source || "",
        source: dividend.source || "",
        statusNote: dividend.status_note || "",
      };
    });
};

renderQuarterlyDividends = function renderQuarterlyDividends(dividends, trades) {
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
    setText("latestDividend54cNote", "尚無配息事件");
    setText("latestDividendHealth", "--");
    const chart = $("dividendCompositionChart");
    if (chart) chart.innerHTML = "<div class='empty'>尚無配息資料</div>";
    renderDividendEstimateTable([]);
    return;
  }

  setText("latestDividendExDate", latest.exDate || "--");
  setText("latestDividendPayDate", `發放日 ${latest.payDate || "--"}`);
  setText("latestDividendPerShare", latest.perShare ? `${fmt.money(latest.perShare, 2)} 元` : "--");
  setText("latestDividendShares", latest.isTracked ? `${fmt.money(latest.shares)} 股` : "--");
  setText("latestDividendCash", latest.isTracked ? `$${fmt.money(latest.cash)}` : "--");
  setText("latestDividend54c", latest.hasComposition && latest.isTracked ? `$${fmt.money(latest.estimated54c)}` : "待補");
  setText(
    "latestDividend54cNote",
    latest.hasComposition
      ? `股利所得比例 ${fmt.pct(latest.dividendIncomePct)}｜${dividendSourceText(latest)}`
      : `54C 組成待補｜${dividendSourceText(latest)}`
  );
  setText(
    "latestDividendHealth",
    !latest.isTracked
      ? "--"
      : !latest.hasComposition
      ? "待補"
      : latest.healthPremium > 0
      ? `$${fmt.money(latest.healthPremium)}`
      : "未達觀察門檻"
  );

  drawDividendCompositionChart(rows);
  renderDividendEstimateTable(rows);
};

ensureDividendCompositionChart = function ensureDividendCompositionChart() {
  if ($("dividendCompositionChart")) return;
  const layout = document.querySelector(".quarterly-layout");
  if (!layout) return;
  const card = document.createElement("div");
  card.className = "dividend-composition-card";
  card.innerHTML = `
    <div class="dividend-composition-head">
      <div>
        <h4>每季配息組成</h4>
        <p>柱高代表每股配息；若 54C / 收益平準金 / 資本利得尚未公告，先以待補柱顯示配息金額。</p>
      </div>
      <div class="dividend-composition-legend">
        <span><i class="legend-dot income"></i>股利所得</span>
        <span><i class="legend-dot equalization"></i>收益平準金</span>
        <span><i class="legend-dot capital"></i>資本利得</span>
        <span><i class="legend-dot other"></i>其他 / 未分類</span>
        <span><i class="legend-dot pending"></i>組成待補</span>
      </div>
    </div>
    <div id="dividendCompositionChart" class="dividend-composition-chart"></div>
  `;
  layout.parentNode.insertBefore(card, layout);
};

drawDividendCompositionChart = function drawDividendCompositionChart(rows) {
  const chart = $("dividendCompositionChart");
  if (!chart) return;
  const chronological = [...(rows || [])].sort((a, b) => String(a.exDate).localeCompare(String(b.exDate)));
  if (!chronological.length) {
    chart.innerHTML = "<div class='empty'>尚無配息資料</div>";
    return;
  }

  const grouped = groupRowsByYear(chronological);
  const barW = Math.max(18, Math.min(54, 720 / Math.max(chronological.length, 1)));
  const quarterGap = barW + 16;
  const yearGap = Math.max(78, barW * 1.4);
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
    const segments = row.hasComposition
      ? [
          { h: totalH * row.dividendIncomePct / 100, color: "#1f8f5f" },
          { h: totalH * row.equalizationPct / 100, color: "#d99b2b" },
          { h: totalH * row.capitalGainPct / 100, color: "#6f63c6" },
          { h: totalH * Math.max(0, row.otherPct || 0) / 100, color: "#b9c3c8" },
        ]
      : [{ h: totalH, color: "#b9c3c8" }];
    let top = barBase;
    const segmentRects = segments.map((seg) => {
      top -= seg.h;
      return `<rect x="${xx}" y="${top}" width="${barW}" height="${Math.max(0, seg.h)}" fill="${seg.color}" />`;
    }).join("");
    const payload = encodeURIComponent(JSON.stringify({ ...row, annualPerShare: yearlyTotals.get(row.year) || 0 }));
    const pendingMark = row.hasComposition ? "" : `<text class="axis-text pending-label" text-anchor="middle" x="${xFor(row)}" y="${Math.max(pad.top + 14, top - 8)}">待補</text>`;
    return `
      <g>
        ${segmentRects}
        ${pendingMark}
        <rect class="composition-hover" data-row="${payload}" x="${xx - 8}" y="${pad.top}" width="${barW + 16}" height="${plotH}" />
      </g>
    `;
  });

  const yearLabels = yearCenters.map(({ year, x }) =>
    `<text class="axis-text year-label" text-anchor="middle" x="${pad.left + centerOffset + x}" y="${height - 22}">${year}</text>`
  );

  chart.innerHTML = `
    <svg width="${width}" height="${height}" style="width:${width}px; min-width:${width}px; max-width:none; height:${height}px;" viewBox="0 0 ${width} ${height}" role="img" aria-label="00919 每季配息組成直條圖">
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
};

bindDividendCompositionTooltip = function bindDividendCompositionTooltip(chart) {
  const tooltip = chart.querySelector("#compositionTooltip");
  if (!tooltip) return;
  chart.querySelectorAll(".composition-hover").forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      const row = JSON.parse(decodeURIComponent(zone.dataset.row));
      const detail = row.hasComposition
        ? `
          <div><span>股利所得</span><b>${fmt.pct(Number(row.dividendIncomePct))}</b></div>
          <div><span>收益平準金</span><b>${fmt.pct(Number(row.equalizationPct))}</b></div>
          <div><span>資本利得</span><b>${fmt.pct(Number(row.capitalGainPct))}</b></div>
          <div><span>其他 / 未分類</span><b>${fmt.pct(Number(row.otherPct || 0))}</b></div>
          <div><span>54C 每股估算</span><b>${fmt.money(Number(row.estimated54cPerShare || 0), 4)} 元</b></div>
        `
        : `<div><span>組成狀態</span><b>pending，待 TWSE / 官方補齊</b></div>`;
      tooltip.innerHTML = `
        <strong>${row.exDate} 每股 ${fmt.money(Number(row.perShare), 2)} 元</strong>
        ${detail}
        <div><span>年度每股合計</span><b>${fmt.money(Number(row.annualPerShare), 2)} 元</b></div>
        <div><span>資料來源</span><b>${typeof sourceTooltipHtml === "function" ? sourceTooltipHtml(dividendSourceText(row)) : dividendSourceText(row)}</b></div>
      `;
      tooltip.classList.add("show");
    });
    zone.addEventListener("mousemove", (event) => {
      const box = chart.getBoundingClientRect();
      const left = Math.min(event.clientX - box.left + 16, box.width - 300);
      const top = Math.max(event.clientY - box.top - 18, 10);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    });
    zone.addEventListener("mouseleave", () => tooltip.classList.remove("show"));
  });
};

renderDividendEstimateTable = function renderDividendEstimateTable(rows) {
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
        <th>狀態 / 來源</th>
      </tr>
    </thead>
    <tbody id="dividendTableBody">
      ${displayRows.map((item) => {
        if (item.type === "annual") {
          return `
            <tr class="annual-summary-row">
              <td>${item.year}</td>
              <td></td><td></td><td></td><td></td><td></td>
              <td>${item.year} 每股 ${fmt.money(item.perShareTotal, 2)} 元，共 ${item.count} 次</td>
              <td></td>
            </tr>
          `;
        }
        const row = item.row;
        const healthText = !row.hasComposition
          ? `<span class="dividend-pending">待補</span>`
          : row.healthPremium > 0
          ? `<span class="dividend-risk">$${fmt.money(row.healthPremium)}</span>`
          : `<span class="dividend-ok">未達</span>`;
        const c54Text = !row.hasComposition
          ? `<span class="dividend-pending">待補</span>`
          : `$${fmt.money(row.estimated54c)}`;
        return `
          <tr class="${row.hasComposition ? "" : "pending-dividend-row"}">
            <td>${row.exDate || "--"}</td>
            <td>${row.payDate || "--"}</td>
            <td>${row.isTracked ? `${fmt.money(row.shares)} 股` : ""}</td>
            <td>${row.isTracked ? `$${fmt.money(row.cash)}` : ""}</td>
            <td>${row.isTracked ? c54Text : ""}</td>
            <td>${row.isTracked ? healthText : ""}</td>
            <td>${item.showAnnual ? `${row.year} 每股 ${fmt.money(item.perShareTotal, 2)} 元，共 ${item.count} 次` : ""}</td>
            <td><span class="source-note-pill">${dividendStatusText(row)}</span><br><small>${typeof sourceTooltipHtml === "function" ? sourceTooltipHtml(dividendSourceText(row)) : dividendSourceText(row)}</small></td>
          </tr>
        `;
      }).join("")}
    </tbody>
  `;
};

buildDividendEstimateRows = function buildDividendEstimateRows(rows) {
  const currentYear = String(new Date().getFullYear());
  return Array.from(groupRowsByYear(rows || []).entries())
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
};

function ensureDividendPendingLegend() {
  const legend = document.querySelector(".dividend-composition-legend");
  if (!legend) return;
  if (!legend.querySelector(".legend-dot.other")) {
    legend.insertAdjacentHTML("beforeend", '<span><i class="legend-dot other"></i>其他 / 未分類</span>');
  }
  if (!legend.querySelector(".legend-dot.pending")) {
    legend.insertAdjacentHTML("beforeend", '<span><i class="legend-dot pending"></i>組成待補</span>');
  }
}

setTimeout(() => {
  if (typeof state !== "undefined" && state.data) render();
  ensureDividendPendingLegend();
}, 0);

let dividendLegendTries = 0;
const dividendLegendTimer = setInterval(() => {
  ensureDividendPendingLegend();
  dividendLegendTries += 1;
  if (dividendLegendTries >= 10 || document.querySelector(".legend-dot.pending")) {
    clearInterval(dividendLegendTimer);
  }
}, 250);
