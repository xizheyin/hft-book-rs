// Small, dependency-free reading aids. Mermaid is initialized by
// mdbook-mermaid/mermaid-init.js; keeping that responsibility in one place
// avoids duplicate rendering and removes the need for a runtime CDN fallback.
document.addEventListener("DOMContentLoaded", function () {
    addReadingProgress();
    wrapWideTables();
    labelScrollableDiagrams();
    addCurrentChapterToc();
});

function addReadingProgress() {
    var bar = document.createElement("div");
    bar.className = "book-reading-progress";
    bar.setAttribute("aria-hidden", "true");
    document.body.appendChild(bar);

    var scheduled = false;
    function update() {
        var root = document.documentElement;
        var scrollable = root.scrollHeight - root.clientHeight;
        var ratio = scrollable > 0 ? root.scrollTop / scrollable : 0;
        bar.style.width = Math.min(100, Math.max(0, ratio * 100)) + "%";
        scheduled = false;
    }

    function scheduleUpdate() {
        if (scheduled) return;
        scheduled = true;
        window.requestAnimationFrame(update);
    }

    update();
    window.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
}

function wrapWideTables() {
    document.querySelectorAll(".content main table").forEach(function (table) {
        if (table.parentElement && table.parentElement.classList.contains("table-scroll")) return;

        var wrapper = document.createElement("div");
        wrapper.className = "table-scroll";
        wrapper.setAttribute("role", "region");
        wrapper.setAttribute("aria-label", "可横向滚动的数据表");
        wrapper.setAttribute("tabindex", "0");
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });
}

function labelScrollableDiagrams() {
    document.querySelectorAll(".content main .mermaid").forEach(function (diagram) {
        diagram.setAttribute("role", "region");
        diagram.setAttribute("aria-label", "可横向滚动的架构或流程图");
        diagram.setAttribute("tabindex", "0");
    });
}

function addCurrentChapterToc() {
    // mdBook 0.5+ renders its own on-this-page tree. Keep the fallback only
    // for older themes so the sidebar never contains two identical TOCs.
    if (document.querySelector(".sidebar .on-this-page")) return;

    var activeChapter = document.querySelector(".sidebar .chapter a.active");
    if (!activeChapter) return;

    var activeChapterItem = activeChapter.closest("li.chapter-item");
    if (!activeChapterItem) return;

    var headers = Array.from(document.querySelectorAll(".content main h2, .content main h3"))
        .filter(function (header) { return Boolean(header.id); });
    if (headers.length === 0) return;

    var existing = activeChapterItem.querySelector("ol.generated-toc");
    if (existing) existing.remove();

    var list = document.createElement("ol");
    list.className = "generated-toc";

    var linksById = new Map();
    headers.forEach(function (header) {
        var item = document.createElement("li");
        item.className = "chapter-item section-link";
        if (header.tagName === "H3") item.classList.add("h3-section");

        var link = document.createElement("a");
        link.href = "#" + header.id;
        link.textContent = header.textContent.replace(/^#+\s*/, "");
        link.className = "sidebar-link";
        item.appendChild(link);
        list.appendChild(item);
        linksById.set(header.id, link);
    });

    activeChapterItem.appendChild(list);

    if (!("IntersectionObserver" in window)) return;

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;
            linksById.forEach(function (link) { link.classList.remove("current-section"); });
            var current = linksById.get(entry.target.id);
            if (current) current.classList.add("current-section");
        });
    }, { rootMargin: "-12% 0px -76% 0px", threshold: 0 });

    headers.forEach(function (header) { observer.observe(header); });
}
