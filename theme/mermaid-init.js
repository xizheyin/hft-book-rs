// 动态加载 Mermaid 并初始化
(function() {
    var script = document.createElement('script');
    script.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
    script.onload = function() {
        mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
    };
    document.head.appendChild(script);
})();
