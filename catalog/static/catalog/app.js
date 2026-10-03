// Progressive enhancement only. Every action also works as a plain link or form.
(() => {
  const lightbox = document.querySelector(".lightbox");
  const openMenus = () => document.querySelectorAll("details.menu[open]");

  const setZoom = (open) => {
    if (!lightbox) return;
    lightbox.classList.toggle("open", open);
    if (!open && location.hash === "#zoom") {
      location.hash = "";
      history.replaceState(null, "", location.pathname + location.search);
    }
  };

  document.addEventListener("click", (event) => {
    for (const menu of openMenus()) {
      if (!menu.contains(event.target)) menu.open = false;
    }
    if (event.target.closest('a[href="#zoom"]')) {
      event.preventDefault();
      setZoom(true);
    } else if (event.target.closest("[data-close-zoom]")) {
      event.preventDefault();
      setZoom(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    const typing = event.target.closest("input, textarea, select");
    if (event.key === "Escape") {
      if (openMenus().length) {
        openMenus().forEach((menu) => { menu.open = false; });
      } else if (lightbox?.classList.contains("open") || location.hash === "#zoom") {
        setZoom(false);
      } else if (!typing) {
        document.querySelector("[data-close]")?.click();
      }
    } else if (event.key === "/" && !typing) {
      event.preventDefault();
      document.querySelector(".search input")?.focus();
    }
  });
})();
