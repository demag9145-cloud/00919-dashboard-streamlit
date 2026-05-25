const baseRenderForYearlyTax = render;
render = function renderWithYearlyTax() {
  baseRenderForYearlyTax();
  renderYearlyTaxPage();
};

function renderYearlyTaxPage() {
  if (!state?.data) return;
  const rows = calcYearlyTaxRows(state.data.dividends || [], state.trades || []);
  const signal = calcYearlyTaxSignal(rows);
  renderYearlyTaxSignal(signal);
  renderYearlyTaxSummary(rows);
  drawYearlyTaxChart(rows);
  renderYearlyTaxTable(rows);
}

function calcYearlyTaxRows(dividends, trades) {
  const settings = typeof window.getSignalSettings === "function"
    ? window.getSignalSettings()
    : { single54cThreshold: HEALTH_PREMIUM_THRESHOLD, supplementalPremiumRatePct: HEALTH_PREMIUM_RATE * 100 };
  const single54cThreshold = Number(settings.single54cThreshold ?? HEALTH_PREMIUM_THRESHOLD);
  const supplementalPremiumRate = Number(settings.supplementalPremiumRatePct ?? HEALTH_PREMIUM_RATE * 100) / 100;
  const sortedTrades = [...trades].sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date)));
  const grouped = new Map();
  [...dividends]
    .sort((a, b) => String(a.ex_date).localeCompare(String(b.ex_date)))
    .forEach((dividend) => {
      const exDate = dividend.ex_date || "";
      const year = exDate.slice(0, 4);
      const shares = calcSharesOnDate(sortedTrades, exDate);
      if (!shares) return;
      const cash = shares * Number(dividend.dividend_per_share || 0);
      const estimated54c = shares * Number(dividend.estimated_54c_per_share || 0);
      const premium = estimated54c >= single54cThreshold ? estimated54c * supplementalPremiumRate : 0;
      if (!grouped.has(year)) {
        grouped.set(year, {
          year,
          count: 0,
          cash: 0,
          estimated54c: 0,
          premium: 0,
          maxSingle54c: 0,
        });
      }
      const row = grouped.get(year);
      row.count += 1;
      row.cash += cash;
      row.estimated54c += estimated54c;
      row.premium += premium;
      row.maxSingle54c = Math.max(row.maxSingle54c, estimated54c);
    });
  return Array.from(grouped.values())
    .map((row) => ({
      ...row,
      non54c: Math.max(0, row.cash - row.estimated54c),
      ratio54c: row.cash ? (row.estimated54c / row.cash) * 100 : 0,
      status: row.count >= 4 ? "完整年度" : "未完整",
    }))
    .sort((a, b) => String(a.year).localeCompare(String(b.year)));
}

function calcYearlyTaxSignal(rows) {
  if (!rows.length) {
    return { level: "unknown", label: "年度燈號：資料不足", reason: "目前沒有除息日持股資料可估算年度稅務。" };
  }
  const settings = typeof window.getSignalSettings === "function"
    ? window.getSignalSettings()
    : { single54cThreshold: HEALTH_PREMIUM_THRESHOLD, supplementalPremiumWarningAmount: 0 };
  const single54cThreshold = Number(settings.single54cThreshold ?? HEALTH_PREMIUM_THRESHOLD);
  const supplementalPremiumWarningAmount = Number(settings.supplementalPremiumWarningAmount ?? 0);
  const latest = rows[rows.length - 1];
  if (latest.premium > supplementalPremiumWarningAmount || latest.maxSingle54c >= single54cThreshold) {
    return {
      level: "yellow",
      label: "年度燈號：黃燈",
      reason: `${latest.year} 已有單次 54C 達補充保費觀察門檻，先預留稅務現金流。`,
    };
  }
  return {
    level: "green",
    label: "年度燈號：綠燈",
    reason: `${latest.year} 目前 54C 與補充保費估算未達觀察門檻。`,
  };
}

function renderYearlyTaxSignal(signal) {
  const light = $("yearlySignalLight");
  if (light) light.className = `mini-signal-light ${signal.level || "yellow"}`;
  setText("yearlySignalLabel", signal.label);
  setText("yearlySignalReason", signal.reason);
}

function renderYearlyTaxSummary(rows) {
  const latest = rows[rows.length - 1];
  if (!latest) {
    setText("yearlyLatestCash", "--");
    setText("yearlyLatest54c", "--");
    setText("yearlyLatestPremium", "--");
    setText("yearlyLatestCount", "--");
    setText("yearlyLatestStatus", "--");
    return;
  }
  setText("yearlyLatestCash", `$${fmt.money(latest.cash)}`);
  setText("yearlyLatest54c", `$${fmt.money(latest.estimated54c)}`);
  setText("yearlyLatestPremium", latest.premium > 0 ? `$${fmt.money(latest.premium)}` : "未達");
  setText("yearlyLatestCount", `${latest.count} 次`);
  setText("yearlyLatestStatus", `${latest.year} ${latest.status}`);
}

function drawYearlyTaxChart(rows) {
  const chart = $("yearlyTaxChart");
  if (!chart) return;
  if (!rows.length) {
    chart.innerHTML = "<div class='empty'>目前沒有可估算的年度稅務資料。</div>";
    return;
  }
  const width = Math.max(760, rows.length * 120 + 180);
  const height = 420;
  const pad = { top: 34, right: 82, bottom: 58, left: 82 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const maxValue = Math.max(...rows.map((row) => row.cash), 1) * 1.15;
  const maxRatio = Math.max(100, Math.ceil(Math.max(...rows.map((row) => row.ratio54c), 1) / 10) * 10);
  const x = (index) => pad.left + (index + 0.5) * (plotW / rows.length);
  const barW = Math.min(58, Math.max(34, plotW / rows.length * 0.38));
  const baseY = pad.top + plotH;
  const y = (value) => scale(value, 0, maxValue, baseY, pad.top);
  const grid = [0, 1, 2, 3, 4].map((i) => {
    const value = maxValue * (i / 4);
    const yy = y(value);
    return `
      <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" />
      <text class="axis-text" x="16" y="${yy + 4}">$${fmt.money(value)}</text>
    `;
  });
  const yRatio = (value) => scale(value, 0, maxRatio, baseY, pad.top);
  const ratioAxis = [0, 25, 50, 75, 100].map((value) => {
    const yy = yRatio(value);
    return `<text class="axis-text" text-anchor="end" x="${width - 12}" y="${yy + 4}">${value}%</text>`;
  });
  const ratioPath = rows.map((row, index) => `${index ? "L" : "M"} ${x(index)} ${yRatio(row.ratio54c)}`).join(" ");
  const bars = rows.map((row, index) => {
    const xx = x(index) - barW / 2;
    const h54c = baseY - y(row.estimated54c);
    const hNon54c = baseY - y(row.non54c);
    const y54c = baseY - h54c;
    const yNon54c = y54c - hNon54c;
    const payload = encodeURIComponent(JSON.stringify(row));
    return `
      <rect x="${xx}" y="${yNon54c}" width="${barW}" height="${Math.max(0, hNon54c)}" fill="#9fb2bd">
        <title>${row.year} 配息總額：$${fmt.money(row.cash)}</title>
      </rect>
      <rect x="${xx}" y="${y54c}" width="${barW}" height="${Math.max(0, h54c)}" fill="#1f8f5f">
        <title>${row.year} 54C 金額：$${fmt.money(row.estimated54c)}</title>
      </rect>
      <circle cx="${x(index)}" cy="${yRatio(row.ratio54c)}" r="4.5" fill="#c2410c">
        <title>${row.year} 54C 占比：${fmt.pct(row.ratio54c)}；補充保費：${row.premium > 0 ? `$${fmt.money(row.premium)}` : "未達"}</title>
      </circle>
      <rect class="yearly-hover" data-row="${payload}" x="${x(index) - 46}" y="${pad.top}" width="92" height="${plotH}" />
      <text class="axis-text" text-anchor="middle" x="${x(index)}" y="${height - 24}">${row.year}</text>
    `;
  });
  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" style="width:${width}px; max-width:none;" role="img" aria-label="年度配息與稅務總覽">
      ${grid.join("")}
      ${ratioAxis.join("")}
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${baseY}" y2="${baseY}" stroke="#bdc8cd" />
      ${bars.join("")}
      <path d="${ratioPath}" fill="none" stroke="#c2410c" stroke-width="3" />
      <text class="axis-text" x="${pad.left}" y="22">金額</text>
      <text class="axis-text" text-anchor="end" x="${width - pad.right + 64}" y="22">54C 占比</text>
    </svg>
    <div id="yearlyTaxTooltip" class="yearly-tax-tooltip"></div>
  `;
  bindYearlyTaxTooltip(chart);
}

function bindYearlyTaxTooltip(chart) {
  const tooltip = chart.querySelector("#yearlyTaxTooltip");
  if (!tooltip) return;
  chart.querySelectorAll(".yearly-hover").forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      const row = JSON.parse(decodeURIComponent(zone.dataset.row));
      tooltip.innerHTML = `
        <strong>${row.year} 年度稅務估算</strong>
        <div><span>配息總額</span><b>$${fmt.money(row.cash)}</b></div>
        <div><span>54C 金額</span><b>$${fmt.money(row.estimated54c)}</b></div>
        <div><span>54C 占比</span><b>${fmt.pct(row.ratio54c)}</b></div>
        <div><span>補充保費</span><b>${row.premium > 0 ? `$${fmt.money(row.premium)}` : "未達"}</b></div>
        <div><span>年度狀態</span><b>${row.status}</b></div>
      `;
      tooltip.classList.add("show");
    });
    zone.addEventListener("mousemove", (event) => {
      const box = chart.getBoundingClientRect();
      const left = Math.min(event.clientX - box.left + 16 + chart.scrollLeft, chart.scrollWidth - 240);
      const top = Math.max(event.clientY - box.top - 18, 10);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    });
    zone.addEventListener("mouseleave", () => tooltip.classList.remove("show"));
  });
}

function renderYearlyTaxTable(rows) {
  const body = $("yearlyTaxTableBody");
  if (!body) return;
  body.innerHTML = rows.length
    ? [...rows].reverse().map((row) => `
      <tr>
        <td>${row.year}</td>
        <td>${row.count}</td>
        <td>$${fmt.money(row.cash)}</td>
        <td>$${fmt.money(row.estimated54c)}</td>
        <td>${row.premium > 0 ? `$${fmt.money(row.premium)}` : "未達"}</td>
        <td>${fmt.pct(row.ratio54c)}</td>
        <td>${row.status}</td>
      </tr>
    `).join("")
    : "<tr><td colspan='7'>目前沒有可估算的年度稅務資料。</td></tr>";
}

setTimeout(() => {
  if (typeof state !== "undefined" && state.data) renderYearlyTaxPage();
}, 0);
