

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
