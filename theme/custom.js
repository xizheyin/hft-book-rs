

// --- Mermaid Support ---
document.addEventListener("DOMContentLoaded", function () {
    // Convert code blocks to mermaid divs
    var codes = document.querySelectorAll("code.language-mermaid");
    codes.forEach(function (code) {
        var pre = code.parentElement;
        var div = document.createElement("div");
        div.className = "mermaid";
        div.textContent = code.textContent;
        pre.replaceWith(div);
    });

    // Load mermaid from CDN if not already loaded
    if (typeof mermaid === "undefined") {
        var script = document.createElement('script');
        script.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
        script.onload = function () {
            mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
        };
        document.head.appendChild(script);
    } else {
        mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
    }
});

// --- Sidebar Table of Contents Support ---
document.addEventListener("DOMContentLoaded", function () {
    // 1. Find the active chapter in the sidebar
    var activeChapter = document.querySelector(".sidebar .chapter-item.expanded > a.active");
    if (!activeChapter) {
        // Fallback: try to find the active link if structure is different
        activeChapter = document.querySelector(".sidebar .chapter-item > a.active");
    }

    if (!activeChapter) return;

    // 2. Find all H2 and H3 headers in the content
    var headers = document.querySelectorAll(".content main h2, .content main h3");
    if (headers.length === 0) return;

    // 3. Create a sub-list for the sidebar
    var ul = document.createElement("ol");
    ul.className = "section generated-toc"; // Add a specific class for styling

    headers.forEach(function (header) {
        // Skip headers without ID (cannot link)
        if (!header.id) return;

        var li = document.createElement("li");
        li.className = "chapter-item section-link";

        var a = document.createElement("a");
        a.href = "#" + header.id;
        a.textContent = header.textContent.replace(/^#+\s*/, ''); // Remove leading # if any
        a.className = "sidebar-link";

        // Add class for H3 to style in CSS
        if (header.tagName === "H3") {
            li.classList.add("h3-section");
        }

        li.appendChild(a);
        ul.appendChild(li);
    });

    // 4. Append the list after the active chapter link
    // We append it to the parent li, so it sits inside the expanded block
    activeChapter.parentElement.appendChild(ul);
});

