drawDividendCompositionChart = function drawDividendCompositionChart(rows) {
  const chart = $("dividendCompositionChart");
  if (!chart) return;
  const chronological = [...rows].sort((a, b) => String(a.exDate).localeCompare(String(b.exDate)));
  if (!chronological.length) {
    chart.innerHTML = "<div class='empty'>尚無配息組成資料</div>";
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
    const incomeH = totalH * row.dividendIncomePct / 100;
    const equalizationH = totalH * row.equalizationPct / 100;
    const capitalH = totalH * row.capitalGainPct / 100;
    const otherPct = Math.max(0, 100 - row.dividendIncomePct - row.equalizationPct - row.capitalGainPct);
    const otherH = totalH * otherPct / 100;
    let top = barBase;
    const segments = [
      { h: incomeH, color: "#1f8f5f" },
      { h: equalizationH, color: "#d99b2b" },
      { h: capitalH, color: "#6f63c6" },
      { h: otherH, color: "#b9c3c8" },
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

buildDividendEstimateRows = function buildDividendEstimateRows(rows) {
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
};

bindDividendCompositionTooltip = function bindDividendCompositionTooltip(chart) {
  const tooltip = chart.querySelector("#compositionTooltip");
  if (!tooltip) return;
  chart.querySelectorAll(".composition-hover").forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      const row = JSON.parse(decodeURIComponent(zone.dataset.row));
      const otherPct = Math.max(
        0,
        100 - Number(row.dividendIncomePct) - Number(row.equalizationPct) - Number(row.capitalGainPct)
      );
      tooltip.innerHTML = `
        <strong>${row.exDate} 每股 ${fmt.money(Number(row.perShare), 2)} 元</strong>
        <div><span>股利所得</span><b>${fmt.pct(Number(row.dividendIncomePct))}</b></div>
        <div><span>收益平準金</span><b>${fmt.pct(Number(row.equalizationPct))}</b></div>
        <div><span>資本利得</span><b>${fmt.pct(Number(row.capitalGainPct))}</b></div>
        <div><span>其他 / 未分類</span><b>${fmt.pct(otherPct)}</b></div>
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
};

setTimeout(() => {
  if (typeof state !== "undefined" && state.data) render();
  ensureOtherLegend();
}, 0);

function ensureOtherLegend() {
  const legend = document.querySelector(".dividend-composition-legend");
  if (legend && !legend.querySelector(".legend-dot.other")) {
    legend.insertAdjacentHTML("beforeend", '<span><i class="legend-dot other"></i>其他 / 未分類</span>');
  }
}

let otherLegendTries = 0;
const otherLegendTimer = setInterval(() => {
  ensureOtherLegend();
  otherLegendTries += 1;
  if (otherLegendTries >= 10 || document.querySelector(".legend-dot.other")) {
    clearInterval(otherLegendTimer);
  }
}, 250);
