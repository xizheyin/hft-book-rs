document.addEventListener("DOMContentLoaded", function () {
    // 1. 配置 Giscus (请替换为你自己的 GitHub Repo 信息)
    const giscusConfig = {
        src: "https://giscus.app/client.js",
        "data-repo": "xizheyin/hft-book-rs",
        "data-repo-id": "R_kgDORXybfg",
        "data-category": "Announcements",
        "data-category-id": "DIC_kwDORXybfs4C3LRE",
        "data-mapping": "title",
        "data-strict": "0",
        "data-reactions-enabled": "1",
        "data-emit-metadata": "0",
        "data-input-position": "bottom",
        "data-theme": "preferred_color_scheme",
        "data-lang": "zh-CN",
        "data-loading": "lazy",
        crossorigin: "anonymous",
        async: true
    };

    // 2. 创建侧边栏容器
    const sidebar = document.createElement("div");
    sidebar.className = "giscus-sidebar";
    sidebar.id = "giscus-sidebar";

    // 添加标题和关闭按钮
    const header = document.createElement("div");
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.alignItems = "center";
    header.style.marginBottom = "20px";
    header.innerHTML = `
        <h3 style="margin:0;">📝 读书笔记</h3>
        <button id="close-giscus" title="关闭侧边栏" style="background:none;border:none;cursor:pointer;font-size:1.5em;color:var(--icons)">×</button>
    `;
    sidebar.appendChild(header);

    // Giscus 挂载点
    const giscusContainer = document.createElement("div");
    giscusContainer.className = "giscus";
    sidebar.appendChild(giscusContainer);

    document.body.appendChild(sidebar);

    // 3. 加载 Giscus 脚本的函数
    let isGiscusLoaded = false;
    function loadGiscus() {
        if (isGiscusLoaded) return;

        const script = document.createElement("script");
        Object.entries(giscusConfig).forEach(([key, value]) => {
            script.setAttribute(key, value);
        });
        giscusContainer.appendChild(script);
        isGiscusLoaded = true;
    }

    // 4. 添加工具栏按钮
    const menu = document.querySelector(".left-buttons");
    if (menu) {
        const btn = document.createElement("button");
        btn.id = "giscus-toggle";
        btn.className = "icon-button giscus-toggle-btn";
        btn.title = "打开/关闭 笔记";
        btn.innerHTML = `<i class="fa fa-commenting-o"></i>`; // 使用 FontAwesome 图标

        // 插入到搜索按钮之前
        const searchBtn = document.getElementById("search-toggle");
        if (searchBtn) {
            menu.insertBefore(btn, searchBtn);
        } else {
            menu.appendChild(btn);
        }

        // 绑定点击事件
        btn.addEventListener("click", function () {
            sidebar.classList.toggle("open");
            document.body.classList.toggle("giscus-open"); // 切换 body class 以挤压内容
            if (sidebar.classList.contains("open")) {
                loadGiscus(); // 首次打开时才加载
            }
        });
    }

    // 关闭按钮事件
    document.getElementById("close-giscus").addEventListener("click", function () {
        sidebar.classList.remove("open");
        document.body.classList.remove("giscus-open"); // 恢复内容宽度
    });

    // 监听主题变化，同步更新 Giscus 主题
    const html = document.documentElement;
    const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            if (mutation.type === "attributes" && mutation.attributeName === "class") {
                // 向 Giscus iframe 发送消息更新主题
                const iframe = document.querySelector('iframe.giscus-frame');
                if (!iframe) return;
                const theme = html.classList.contains('light') ? 'light' : 'dark'; // 简化处理，可根据 mdbook 具体类名优化
                iframe.contentWindow.postMessage({
                    giscus: {
                        setConfig: {
                            theme: theme
                        }
                    }
                }, 'https://giscus.app');
            }
        });
    });
    observer.observe(html, { attributes: true });
});

// --- Mermaid Support ---
document.addEventListener("DOMContentLoaded", function() {
    // Convert code blocks to mermaid divs
    var codes = document.querySelectorAll("code.language-mermaid");
    codes.forEach(function(code) {
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
        script.onload = function() {
            mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
        };
        document.head.appendChild(script);
    } else {
        mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
    }
});
