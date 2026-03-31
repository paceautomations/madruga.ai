/**
 * Mermaid Interactive — Pan+Zoom + Fullscreen Modal
 * Attaches svg-pan-zoom to all rendered Mermaid diagrams.
 * Loaded via <script defer> in Starlight head.
 */
(function () {
  const PROCESSED = new WeakSet();

  function createFullscreenBtn() {
    const btn = document.createElement('button');
    btn.className = 'fullscreen-btn';
    btn.title = 'Fullscreen';
    btn.setAttribute('aria-label', 'Open diagram fullscreen');
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>';
    return btn;
  }

  function openModal(svgEl) {
    const modal = document.createElement('div');
    modal.className = 'mermaid-modal';

    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-btn';
    closeBtn.title = 'Close (Esc)';
    closeBtn.setAttribute('aria-label', 'Close fullscreen');
    closeBtn.innerHTML = '&times;';

    const svgClone = svgEl.cloneNode(true);
    svgClone.removeAttribute('style');
    svgClone.style.width = '100%';
    svgClone.style.height = '100%';

    const container = document.createElement('div');
    container.style.width = '100%';
    container.style.height = '100%';
    container.appendChild(svgClone);

    modal.appendChild(closeBtn);
    modal.appendChild(container);
    document.body.appendChild(modal);
    document.body.style.overflow = 'hidden';

    // Init pan-zoom on modal SVG
    if (window.svgPanZoom) {
      window.svgPanZoom(svgClone, {
        zoomEnabled: true,
        panEnabled: true,
        controlIconsEnabled: true,
        fit: true,
        center: true,
        minZoom: 0.3,
        maxZoom: 10,
      });
    }

    function close() {
      modal.remove();
      document.body.style.overflow = '';
      document.removeEventListener('keydown', onKey);
    }

    function onKey(e) {
      if (e.key === 'Escape') close();
    }

    closeBtn.addEventListener('click', close);
    modal.addEventListener('click', function (e) {
      if (e.target === modal) close();
    });
    document.addEventListener('keydown', onKey);
  }

  function enhanceDiagram(pre) {
    if (PROCESSED.has(pre)) return;
    const svg = pre.querySelector('svg');
    if (!svg) return;
    PROCESSED.add(pre);

    // Wrap in container
    const wrapper = document.createElement('div');
    wrapper.className = 'mermaid-container';
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);

    // Ensure SVG has width/height for svg-pan-zoom
    if (!svg.getAttribute('height')) {
      svg.setAttribute('height', svg.getBoundingClientRect().height || 400);
    }

    // Init inline pan-zoom
    if (window.svgPanZoom) {
      window.svgPanZoom(svg, {
        zoomEnabled: true,
        panEnabled: true,
        controlIconsEnabled: true,
        fit: true,
        center: true,
        minZoom: 0.5,
        maxZoom: 5,
      });
    }

    // Add fullscreen button
    const btn = createFullscreenBtn();
    btn.addEventListener('click', function () {
      openModal(svg);
    });
    wrapper.appendChild(btn);
  }

  function enhanceAll() {
    document.querySelectorAll('pre.mermaid[data-processed]').forEach(enhanceDiagram);
  }

  // Observe for diagrams that render after page load
  const observer = new MutationObserver(function (mutations) {
    for (const m of mutations) {
      if (m.type === 'attributes' && m.attributeName === 'data-processed') {
        enhanceDiagram(m.target);
      }
      // Also check added nodes (theme re-render replaces elements)
      if (m.type === 'childList') {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType === 1) {
            if (node.matches && node.matches('pre.mermaid[data-processed]')) {
              enhanceDiagram(node);
            }
            if (node.querySelectorAll) {
              node.querySelectorAll('pre.mermaid[data-processed]').forEach(enhanceDiagram);
            }
          }
        });
      }
    }
  });

  // Start observing
  observer.observe(document.body, {
    attributes: true,
    attributeFilter: ['data-processed'],
    childList: true,
    subtree: true,
  });

  // Handle already-rendered diagrams
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceAll);
  } else {
    enhanceAll();
  }

  // Re-enhance after Astro view transitions
  document.addEventListener('astro:after-swap', function () {
    enhanceAll();
  });
})();
