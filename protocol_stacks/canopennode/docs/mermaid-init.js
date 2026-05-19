(function () {
    const renderMermaid = async () => {
        const mermaidBlocks = document.querySelectorAll("pre code.language-mermaid");
        if (mermaidBlocks.length === 0) {
            return;
        }

        const mermaid = await import("https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs");
        mermaid.default.initialize({ startOnLoad: false });

        for (const [index, block] of mermaidBlocks.entries()) {
            const source = block.textContent;
            const container = document.createElement("div");
            container.className = "mermaid";
            container.textContent = source;
            block.parentElement.replaceWith(container);

            const { svg } = await mermaid.default.render(`mermaid-${index}`, source);
            container.innerHTML = svg;
        }
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", renderMermaid);
    } else {
        renderMermaid();
    }
})();
