const baseRenderForHoldings = render;
render = function renderWithHoldings() {
  baseRenderForHoldings();
  renderHoldingsPage();
};

function renderHoldingsPage() {
  if (!state?.data) return;
  const holdings = state.data.holdings || {};
  const history = state.data.holdings_history || [];
  const top10 = holdings.top10 || [];
  const industries = holdings.industries || [];
  const previous = getPreviousHoldingSnapshot(history, holdings.data_date);

  setText("holdingsDataDate", holdings.data_date ? `持股資料日 ${holdings.data_date}` : "尚未抓到持股資料");
  setText("holdingsLatestDate", holdings.data_date || "--");
  setText("holdingSnapshotCount", `${history.length || 0} 次`);

  const top10Total = top10.reduce((sum, row) => sum + Number(row.weight_pct || 0), 0);
  setText("top10TotalWeight", top10.length ? `${fmt.money(top10Total, 2)}%` : "--");
  setText("topHoldingName", top10[0] ? `${top10[0].name} ${top10[0].code || ""}` : "--");
  setText("topHoldingWeight", top10[0] ? `${fmt.money(top10[0].weight_pct, 2)}%` : "--");
  renderHoldingRotation(top10, previous, holdings.data_date);

  drawHorizontalBarChart("topHoldingsChart", top10, {
    label: (row) => `${row.rank}. ${row.name} (${row.code || "--"})`,
    value: (row) => Number(row.weight_pct || 0),
    title: (row) => {
      const previousByCode = new Map((previous?.top10 || []).map((item) => [item.code, item]));
      const previousRow = previousByCode.get(row.code);
      const change = previousRow ? Number(row.weight_pct || 0) - Number(previousRow.weight_pct || 0) : null;
      const changeText = change === null ? "首次快照" : `${change >= 0 ? "+" : ""}${fmt.money(change, 2)}%`;
      return `${row.name} (${row.code || "--"})
占比：${fmt.money(row.weight_pct, 2)}%
前期變化：${changeText}
持有股數：${fmt.money(row.shares, 0)}`;
    },
    className: "holdings-bar",
    unit: "%",
    empty: "尚未抓到前十大持股資料。",
  });
  drawHorizontalBarChart("industryChart", industries.slice(0, 10), {
    label: (row) => row.industry,
    value: (row) => Number(row.weight_pct || 0),
    className: "industry-bar",
    unit: "%",
    empty: "尚未抓到產業分布資料。",
  });
}

function getHoldingRotation(currentTop10, previousSnapshot) {
  if (!previousSnapshot) return { added: [], removed: [] };
  const currentByCode = new Map(currentTop10.map((row) => [row.code, row]));
  const previousByCode = new Map((previousSnapshot.top10 || []).map((row) => [row.code, row]));
  const added = currentTop10.filter((row) => row.code && !previousByCode.has(row.code));
  const removed = (previousSnapshot.top10 || []).filter((row) => row.code && !currentByCode.has(row.code));
  return { added, removed };
}

function renderHoldingRotation(currentTop10, previousSnapshot, currentDate) {
  const target = $("holdingRotationList");
  const period = $("holdingRotationPeriod");
  const rotation = getHoldingRotation(currentTop10, previousSnapshot);
  const total = rotation.added.length + rotation.removed.length;

  setText("holdingRotationCount", previousSnapshot ? `${total} 檔` : "--");
  setText(
    "holdingRotationSummary",
    previousSnapshot ? `新增 ${rotation.added.length} / 淘汰 ${rotation.removed.length}` : "等待下一次快照"
  );
  if (period) {
    period.textContent = previousSnapshot
      ? `${previousSnapshot.data_date} → ${currentDate || "--"}`
      : "需要至少兩次持股快照才會顯示變動";
  }
  if (!target) return;
  if (!previousSnapshot) {
    target.innerHTML = "<div class='empty'>目前只有第一次快照；下一次資料日更新後，會自動列出新增與淘汰的前十大持股。</div>";
    return;
  }
  const list = (rows, emptyText) =>
    rows.length
      ? `<ul>${rows.map((row) => `<li title="${row.name} ${row.code || ""}，${fmt.money(row.weight_pct, 2)}%">${row.name} ${fmt.money(row.weight_pct, 2)}%</li>`).join("")}</ul>`
      : `<p class="change-flat">${emptyText}</p>`;
  target.innerHTML = `
    <div class="rotation-group rotation-added">
      <strong>新增進前十大</strong>
      ${list(rotation.added, "沒有新增")}
    </div>
    <div class="rotation-group rotation-removed">
      <strong>跌出前十大</strong>
      ${list(rotation.removed, "沒有淘汰")}
    </div>
  `;
}

function getPreviousHoldingSnapshot(history, currentDate) {
  const rows = [...history]
    .filter((row) => row.data_date && row.data_date !== currentDate)
    .sort((a, b) => String(a.data_date).localeCompare(String(b.data_date)));
  return rows[rows.length - 1] || null;
}

function renderHoldingsTable(rows, previousSnapshot) {
  const body = $("holdingsTableBody");
  if (!body) return;
  const previousByCode = new Map((previousSnapshot?.top10 || []).map((row) => [row.code, row]));
  body.innerHTML = rows.length
    ? rows.map((row) => {
      const previous = previousByCode.get(row.code);
      const change = previous ? Number(row.weight_pct || 0) - Number(previous.weight_pct || 0) : null;
      return `
        <tr>
          <td>${row.rank}</td>
          <td>${row.name}</td>
          <td>${row.code || "--"}</td>
          <td>${fmt.money(row.weight_pct, 2)}%</td>
          <td>${formatHoldingChange(change)}</td>
          <td>${fmt.money(row.shares, 0)}</td>
        </tr>
      `;
    }).join("")
    : "<tr><td colspan='6'>尚未抓到前十大持股資料。</td></tr>";
}

function formatHoldingChange(change) {
  if (change === null || !Number.isFinite(change)) return "<span class='change-flat'>首次快照</span>";
  if (Math.abs(change) < 0.005) return "<span class='change-flat'>0.00%</span>";
  const className = change > 0 ? "change-up" : "change-down";
  const sign = change > 0 ? "+" : "";
  return `<span class="${className}">${sign}${fmt.money(change, 2)}%</span>`;
}

function drawHorizontalBarChart(targetId, rows, options) {
  const target = $(targetId);
  if (!target) return;
  if (!rows.length) {
    target.innerHTML = `<div class="empty">${options.empty}</div>`;
    return;
  }
  const width = 760;
  const rowH = 28;
  const pad = { top: 24, right: 52, bottom: 24, left: 128 };
  const height = Math.max(340, pad.top + pad.bottom + rows.length * rowH);
  const plotW = width - pad.left - pad.right;
  const maxValue = Math.max(...rows.map(options.value), 1) * 1.08;
  const bars = rows.map((row, index) => {
    const value = options.value(row);
    const y = pad.top + index * rowH + 4;
    const w = (value / maxValue) * plotW;
    return `
      <text class="axis-text" text-anchor="end" x="${pad.left - 10}" y="${y + 14}">${options.label(row)}</text>
      <rect class="${options.className}" x="${pad.left}" y="${y}" width="${w}" height="16" rx="4">
        <title>${options.title ? options.title(row) : `${options.label(row)} ${fmt.money(value, 2)}${options.unit}`}</title>
      </rect>
      <text class="axis-text" x="${pad.left + w + 8}" y="${y + 13}">${fmt.money(value, 2)}${options.unit}</text>
    `;
  });
  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${targetId}">
      ${bars.join("")}
    </svg>
  `;
}

setTimeout(() => {
  if (typeof state !== "undefined" && state.data) renderHoldingsPage();
}, 0);
