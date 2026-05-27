const navLinks = Array.from(document.querySelectorAll(".nav a[href^='#']"));
const navTargets = navLinks
  .map((link) => ({
    link,
    target: document.querySelector(link.getAttribute("href")),
  }))
  .filter((item) => item.target);
const navObserverTargets = navTargets.filter(({ target }) => target.id !== "home");
const mobileHomeOnlyQuery = window.matchMedia("(max-width: 760px)");

function isMobileHomeOnly() {
  return mobileHomeOnlyQuery.matches;
}

function normalizeMobileHash() {
  if (isMobileHomeOnly() && location.hash && location.hash !== "#home") {
    history.replaceState(null, "", "#home");
    setTimeout(() => window.scrollTo({ top: 0, behavior: "auto" }), 0);
    setActiveNav("#home");
    return true;
  }
  return false;
}

function setActiveNav(hash) {
  navLinks.forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === hash);
  });
}

function isVisibleTarget(target) {
  if (!target) return false;
  return window.getComputedStyle(target).display !== "none";
}

function requestParentNavigation(hash) {
  if (!window.__00919_STREAMLIT_EMBED) return false;
  window.parent.postMessage({ type: "00919:navigate", hash }, "*");
  setActiveNav(hash);
  return true;
}

function scrollToNavTarget(hash, replace = false) {
  if (isMobileHomeOnly() && hash !== "#home") {
    hash = "#home";
    replace = true;
  }
  const target = document.querySelector(hash);
  if (!isVisibleTarget(target)) return;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
  if (replace) {
    history.replaceState(null, "", hash);
  } else {
    history.pushState(null, "", hash);
  }
  setActiveNav(hash);
}

navLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const hash = link.getAttribute("href");
    if (requestParentNavigation(hash)) return;
    scrollToNavTarget(hash);
  });
});

window.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type !== "00919:scroll-to" || !data.hash) return;
  const target = document.querySelector(data.hash);
  if (!isVisibleTarget(target)) return;
  const top = target.getBoundingClientRect().top + window.scrollY;
  window.parent.postMessage({ type: "00919:navigate-offset", hash: data.hash, top }, "*");
  setActiveNav(data.hash);
});

window.addEventListener("popstate", () => {
  if (normalizeMobileHash()) return;
  const hash = location.hash || "#home";
  scrollToNavTarget(hash, true);
});

mobileHomeOnlyQuery.addEventListener("change", () => {
  normalizeMobileHash();
});

const observer = new IntersectionObserver(
  (entries) => {
    if (window.scrollY < 80) {
      setActiveNav("#home");
      return;
    }
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
    if (!visible) return;
    setActiveNav(`#${visible.target.id}`);
  },
  {
    root: null,
    rootMargin: "-20% 0px -65% 0px",
    threshold: 0,
  }
);

navObserverTargets.forEach(({ target }) => observer.observe(target));

if (normalizeMobileHash()) {
  setActiveNav("#home");
} else if (location.hash && document.querySelector(location.hash)) {
  setTimeout(() => scrollToNavTarget(location.hash, true), 0);
} else {
  setActiveNav("#home");
}
