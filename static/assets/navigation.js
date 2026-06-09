(() => {
  const mobileHomeOnlyQuery = window.matchMedia("(max-width: 760px)");
  const desktopPageMap = {
    "#home": [".desktop-home", "#daily"],
    "#trades": [".desktop-home", "#trades"],
    "#monthly": [".desktop-home", "#monthly"],
    "#quarterly": [".desktop-home", "#quarterly"],
    "#holdings": [".desktop-home", "#holdings"],
    "#yearly": [".desktop-home", "#yearly"],
    "#signal-settings": [".desktop-home", "#signal-settings"],
    "#data-maintenance": [".desktop-home", "#data-maintenance"],
    "#manual": [".desktop-home", "#manual"],
  };
  const managedPageSelectors = [
    ".page-header",
    ".desktop-home",
    "#daily",
    "#trades",
    "#monthly",
    "#quarterly",
    "#holdings",
    "#yearly",
    "#signal-settings",
    "#data-maintenance",
    "#manual",
  ];

  function getNavLinks() {
    return Array.from(document.querySelectorAll(".nav a[href^='#']"));
  }

  function isMobileHomeOnly() {
    return mobileHomeOnlyQuery.matches;
  }

  function canonicalHash(hash) {
    const value = String(hash || "#home").trim();
    return Object.prototype.hasOwnProperty.call(desktopPageMap, value) ? value : "#home";
  }

  function setActiveNav(hash) {
    const activeHash = canonicalHash(hash);
    document.body.dataset.activePage = activeHash.slice(1);
    getNavLinks().forEach((link) => {
      const linkHash = canonicalHash(link.getAttribute("href"));
      const isActive = linkHash === activeHash;
      link.classList.remove("active", "is-active");
      if (isActive) {
        link.classList.add("active", "is-active");
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  }

  function getPageElements(hash) {
    const activeHash = canonicalHash(hash);
    return (desktopPageMap[activeHash] || desktopPageMap["#home"])
      .map((selector) => document.querySelector(selector))
      .filter(Boolean);
  }

  function setElementPageVisibility(element, isActive) {
    element.classList.toggle("dashboard-page-hidden", !isActive);
    element.toggleAttribute("hidden", !isActive);
    element.setAttribute("aria-hidden", isActive ? "false" : "true");
  }

  function updateHistory(hash, replace) {
    const activeHash = canonicalHash(hash);
    const currentHash = location.hash || "#home";
    if (replace) {
      history.replaceState(null, "", activeHash);
      return;
    }
    if (currentHash !== activeHash) {
      history.pushState(null, "", activeHash);
    }
  }

  function normalizeMobileHash() {
    if (isMobileHomeOnly() && location.hash && location.hash !== "#home") {
      history.replaceState(null, "", "#home");
      setActiveNav("#home");
      window.setTimeout(() => window.scrollTo({ top: 0, behavior: "auto" }), 0);
      return true;
    }
    return false;
  }

  function notifyRendered(activeHash) {
    const detail = { hash: activeHash };
    try {
      if (window.__00919_STREAMLIT_EMBED && window.parent && window.parent !== window) {
        window.parent.postMessage({
          type: "00919:active-page",
          hash: activeHash,
          page: activeHash.replace(/^#/, "") || "home",
        }, "*");
      }
    } catch (err) {
      /* parent sync is best-effort only */
    }
    window.dispatchEvent(new CustomEvent("dashboard:rendered", { detail }));
    window.requestAnimationFrame(() => {
      setActiveNav(activeHash);
      try {
        if (window.__00919_STREAMLIT_EMBED && window.parent && window.parent !== window) {
          window.parent.postMessage({
            type: "00919:active-page",
            hash: activeHash,
            page: activeHash.replace(/^#/, "") || "home",
          }, "*");
        }
      } catch (err) {}
      window.dispatchEvent(new CustomEvent("dashboard:rendered", { detail }));
    });
  }

  function showPage(hash = "#home", replace = false, shouldScroll = true) {
    let activeHash = canonicalHash(hash);
    if (isMobileHomeOnly() && activeHash !== "#home") {
      activeHash = "#home";
      replace = true;
    }

    const activeElements = new Set(getPageElements(activeHash));
    managedPageSelectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((element) => {
        setElementPageVisibility(element, activeElements.has(element));
      });
    });

    document.body.dataset.activePage = activeHash.slice(1);
    updateHistory(activeHash, replace);
    setActiveNav(activeHash);
    notifyRendered(activeHash);

    if (shouldScroll) {
      window.scrollTo({ top: 0, behavior: "auto" });
    }
  }


  function getNativeTradesUrl() {
    const configured = window.__00919_NATIVE_TRADES_URL || "/?native_page=trades";
    return configured;
  }

  function resolveNativeTradesUrl() {
    const targetUrl = getNativeTradesUrl();
    if (/^https?:\/\//i.test(targetUrl) || targetUrl.startsWith("/")) return targetUrl;
    return "/" + targetUrl.replace(/^\/?/, "");
  }

  function withEmbeddedFlag(url) {
    try {
      const resolved = new URL(url, window.location.href);
      resolved.searchParams.set("native_page", "trades");
      resolved.searchParams.set("embedded", "1");
      resolved.hash = "";
      return resolved.toString();
    } catch (err) {
      return "/?native_page=trades&embedded=1";
    }
  }


  function showNativeTradesFallbackCard(targetUrl) {
    const trades = document.querySelector("#trades");
    if (!trades) return;
    const existing = trades.querySelector(".native-trades-fallback-card");
    if (!existing) {
      const card = document.createElement("div");
      card.className = "native-trades-fallback-card";
      card.innerHTML = `
        <strong>交易紀錄已改為 Streamlit 原生頁</strong>
        <span>新增交易、CSV 匯入與 Google Sheets 寫入都在原生頁執行；若沒有自動切換，請點下方按鈕。</span>
        <a href="${targetUrl}" target="_top" rel="noopener">開啟交易紀錄原生頁</a>
      `;
      const head = trades.querySelector(".section-head");
      if (head && head.nextSibling) head.parentNode.insertBefore(card, head.nextSibling);
      else trades.prepend(card);
    }
    trades.querySelectorAll(".trade-layout, .trade-actions").forEach((element) => {
      element.style.display = "none";
    });
  }

  function navigateToNativeTradesPage() {
    const targetUrl = resolveNativeTradesUrl();
    const iframeSelfUrl = withEmbeddedFlag(targetUrl);
    let requested = false;

    // First try the preferred route: ask the Streamlit parent page to change
    // the real browser URL to ?native_page=trades.  Some Streamlit component
    // sandbox settings block direct top navigation, so this is intentionally
    // paired with a same-frame fallback below.
    try {
      window.parent.postMessage({ type: "00919:navigate", hash: "#trades", nativeUrl: targetUrl }, "*");
      requested = true;
    } catch (err) {
      /* postMessage fallback failed */
    }

    try {
      if (window.top && window.top !== window) {
        window.top.postMessage({ type: "00919:navigate", hash: "#trades", nativeUrl: targetUrl }, "*");
        requested = true;
      }
    } catch (err) {
      /* top postMessage may be blocked */
    }

    // Last-resort but reliable: navigate the dashboard iframe itself to the
    // real Streamlit native trade page.  This still gives the user the native
    // st.form / Google Sheets workflow even when the browser refuses top-level
    // navigation from a sandboxed iframe.
    window.setTimeout(() => {
      try {
        window.location.assign(iframeSelfUrl);
        return;
      } catch (err) {
        /* same-frame navigation failed */
      }
      try {
        window.location.href = iframeSelfUrl;
        return;
      } catch (err) {
        /* href fallback failed */
      }
      if (typeof window.showDashboardPage === "function") {
        window.showDashboardPage("#trades", false, true);
        showNativeTradesFallbackCard(targetUrl);
      }
    }, 180);

    return requested;
  }

  function resolveNativePageUrl(nativePage, configuredUrl) {
    if (configuredUrl) {
      if (/^https?:\/\//i.test(configuredUrl) || configuredUrl.startsWith("/")) return configuredUrl;
      return "/" + configuredUrl.replace(/^\/?/, "");
    }
    const page = nativePage || "data_maintenance";
    if (page === "data_maintenance") return "/?native_page=data_maintenance";
    if (page === "data-maintenance") return "/?target_page=data-maintenance";
    return `/?native_page=${page}`;
  }

  function navigateToNativePage(nativePage, configuredUrl) {
    const targetUrl = resolveNativePageUrl(nativePage, configuredUrl);
    const normalizedPage = String(nativePage || "").replace("_", "-");
    const isDataMaintenance = normalizedPage === "data-maintenance" || targetUrl.includes("target_page=data-maintenance");

    // UI57：資料維護由 Streamlit 原生頁負責。先用 postMessage 請父層
    // 直接改最外層網址；同時送新版與舊版相容訊息，避免瀏覽器殘留舊 bridge
    // 時左鍵點擊沒有反應。
    const payload = {
      type: "00919:navigate-native",
      nativePage: nativePage || "data-maintenance",
      nativeUrl: targetUrl,
      forceTop: true,
    };
    const compatPayload = {
      type: "00919:navigate",
      hash: isDataMaintenance ? "#data-maintenance" : "#trades",
      nativePage: nativePage || "data-maintenance",
      nativeUrl: targetUrl,
      forceTop: true,
    };

    let requested = false;
    function sendTo(win) {
      if (!win || win === window) return;
      try { win.postMessage(payload, "*"); requested = true; } catch (err) {}
      try { win.postMessage(compatPayload, "*"); requested = true; } catch (err) {}
    }
    sendTo(window.parent);
    sendTo(window.top);

    window.setTimeout(() => {
      sendTo(window.parent);
      sendTo(window.top);
      // 不再把資料維護載進 iframe，避免雙更新按鈕；若父層橋接真的失敗，
      // 維持目前畫面，使用者仍可用右鍵開啟。
      if (isDataMaintenance) return;
      try { if (window.top && window.top !== window) { window.top.location.href = targetUrl; return; } } catch (err) {}
      try { window.location.assign(targetUrl); return; } catch (err) {}
      try { window.location.href = targetUrl; return; } catch (err) {}
    }, requested ? 120 : 40);
    return requested;
  }


  document.addEventListener("click", (event) => {
    if (event.defaultPrevented) return;
    const nativePageLink = event.target.closest("a[data-native-page]");
    if (nativePageLink && window.__00919_STREAMLIT_EMBED) {
      const nativePage = nativePageLink.dataset.nativePage || "data-maintenance";
      const nativeUrl = nativePageLink.dataset.nativeUrl || nativePageLink.getAttribute("href") || "/?target_page=data-maintenance";
      event.preventDefault();
      if (nativePage === "data-maintenance") setActiveNav("#data-maintenance");
      navigateToNativePage(nativePage, nativeUrl);
      return;
    }
    const nativeLink = event.target.closest("a[data-native-trades-link]");
    if (nativeLink && window.__00919_STREAMLIT_EMBED && window.__00919_NATIVE_TRADES_ENABLED) {
      event.preventDefault();
      setActiveNav("#trades");
      navigateToNativeTradesPage();
      return;
    }
    const link = event.target.closest("a[href^='#']");
    if (!link) return;
    const rawHash = String(link.getAttribute("href") || "").trim();
    if (!Object.prototype.hasOwnProperty.call(desktopPageMap, rawHash)) return;
    event.preventDefault();

    if (window.__00919_STREAMLIT_EMBED && window.__00919_NATIVE_TRADES_ENABLED && rawHash === "#trades") {
      setActiveNav(rawHash);
      navigateToNativeTradesPage();
      return;
    }

    showPage(rawHash);
  }, true);

  window.addEventListener("message", (event) => {
    const data = event.data || {};
    if (data.type !== "00919:scroll-to" || !data.hash) return;
    const hash = canonicalHash(data.hash);
    showPage(hash, true, false);
    const visiblePage = hash === "#home" ? document.querySelector(".desktop-home") : document.querySelector(hash);
    const fallback = document.querySelector(".content");
    const firstVisible = visiblePage || fallback;
    if (!firstVisible) return;
    const top = firstVisible.getBoundingClientRect().top + window.scrollY;
    window.parent.postMessage({ type: "00919:navigate-offset", hash, top }, "*");
    setActiveNav(hash);
  });

  window.addEventListener("popstate", () => {
    if (normalizeMobileHash()) return;
    showPage(location.hash || "#home", true);
  });

  mobileHomeOnlyQuery.addEventListener("change", () => {
    if (normalizeMobileHash()) return;
    showPage(location.hash || "#home", true, false);
  });

  window.showDashboardPage = showPage;
  window.setDashboardActiveNav = setActiveNav;

  if (normalizeMobileHash()) {
    showPage("#home", true, false);
  } else {
    showPage(location.hash || "#home", true, false);
  }
})();
