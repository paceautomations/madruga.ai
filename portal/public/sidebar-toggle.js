document.addEventListener('DOMContentLoaded', function () {
  // ── Icon SVGs (Lucide-style, 24x24 viewBox) ──
  var icons = [
    {
      label: 'Business',
      svg: '<svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>',
    },
    {
      label: 'Engineering',
      svg: '<svg viewBox="0 0 24 24"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>',
    },
    {
      label: 'Planning',
      svg: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 7h8"/><path d="M8 12h8"/><path d="M8 17h5"/></svg>',
    },
    {
      label: 'ADRs',
      svg: '<svg viewBox="0 0 24 24"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>',
    },
    {
      label: 'Research',
      svg: '<svg viewBox="0 0 24 24"><path d="M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2"/><path d="M8.5 2h7"/><path d="M7 16.5h10"/></svg>',
    },
  ];

  var sectionLabels = icons.map(function (i) { return i.label; });

  // SVG icons for toggle
  var chevronLeftSvg = '<svg viewBox="0 0 24 24"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>';
  var chevronRightSvg = '<svg viewBox="0 0 24 24"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>';

  var collapsed = localStorage.getItem('sidebar-collapsed') === 'true';

  // ── Create the single toggle button ──
  var toggleBtn = document.createElement('button');
  toggleBtn.className = 'sidebar-toggle-btn';
  toggleBtn.setAttribute('aria-label', 'Toggle sidebar');

  // ── Create icon rail ──
  var rail = document.createElement('div');
  rail.className = 'sidebar-icon-rail';

  var railIcons = [];
  icons.forEach(function (icon, i) {
    var el = document.createElement('button');
    el.className = 'rail-icon';
    el.setAttribute('data-tooltip', icon.label);
    el.setAttribute('data-section', icon.label);
    el.setAttribute('aria-label', icon.label);
    el.innerHTML = icon.svg;
    el.addEventListener('click', function () {
      navigateToSection(i);
    });
    rail.appendChild(el);
    railIcons.push(el);
  });

  // ── Detect active section from sidebar ──
  function updateActiveRailIcon() {
    var activeSectionIndex = -1;
    var activeLink = document.querySelector('.sidebar-pane a[aria-current="page"]');
    if (activeLink) {
      var parentDetails = activeLink.closest('details');
      while (parentDetails) {
        var summary = parentDetails.querySelector(':scope > summary .large');
        if (summary) {
          var idx = sectionLabels.indexOf(summary.textContent.trim());
          if (idx !== -1) activeSectionIndex = idx;
        }
        parentDetails = parentDetails.parentElement ? parentDetails.parentElement.closest('details') : null;
      }
    }
    railIcons.forEach(function (icon, i) {
      icon.classList.toggle('active', i === activeSectionIndex);
    });
  }

  // ── State management ──
  function applyState(isCollapsed) {
    if (isCollapsed) {
      document.body.classList.add('sidebar-collapsed');
      toggleBtn.innerHTML = chevronRightSvg;
      toggleBtn.title = 'Expand sidebar (Ctrl+\\)';
      toggleBtn.setAttribute('aria-expanded', 'false');
    } else {
      document.body.classList.remove('sidebar-collapsed');
      toggleBtn.innerHTML = chevronLeftSvg;
      toggleBtn.title = 'Collapse sidebar (Ctrl+\\)';
      toggleBtn.setAttribute('aria-expanded', 'true');
    }
  }

  function navigateToSection(index) {
    collapsed = false;
    localStorage.setItem('sidebar-collapsed', 'false');
    applyState(false);

    setTimeout(function () {
      var summaries = document.querySelectorAll('.sidebar-pane details > summary .large');
      for (var i = 0; i < summaries.length; i++) {
        if (sectionLabels.indexOf(summaries[i].textContent.trim()) === index) {
          var details = summaries[i].closest('details');
          if (details) {
            details.open = true;
            details.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
          break;
        }
      }
    }, 50);
  }

  applyState(collapsed);
  updateActiveRailIcon();

  // ── Toggle click ──
  toggleBtn.addEventListener('click', function () {
    collapsed = !collapsed;
    localStorage.setItem('sidebar-collapsed', String(collapsed));
    applyState(collapsed);
  });

  // ── Keyboard shortcut: Cmd+\ or Ctrl+\ ──
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
      e.preventDefault();
      collapsed = !collapsed;
      localStorage.setItem('sidebar-collapsed', String(collapsed));
      applyState(collapsed);
    }
  });

  // ── Sidebar resize handle ──
  var resizeHandle = document.createElement('div');
  resizeHandle.className = 'sidebar-resize-handle';

  // Only restore saved width if user has explicitly resized before
  var userHasResized = localStorage.getItem('sidebar-resized') === 'true';
  var savedWidth = localStorage.getItem('sidebar-width');
  if (userHasResized && savedWidth && !collapsed) {
    document.documentElement.style.setProperty('--sl-sidebar-width', savedWidth + 'px');
  }

  var isResizing = false;

  resizeHandle.addEventListener('mousedown', function (e) {
    if (collapsed) return;
    isResizing = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', function (e) {
    if (!isResizing) return;
    var newWidth = Math.min(Math.max(e.clientX, 180), 600);
    document.documentElement.style.setProperty('--sl-sidebar-width', newWidth + 'px');
    localStorage.setItem('sidebar-width', String(newWidth));
    localStorage.setItem('sidebar-resized', 'true');
  });

  document.addEventListener('mouseup', function () {
    if (!isResizing) return;
    isResizing = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });

  // ── Inject into DOM ──
  document.body.appendChild(toggleBtn);
  document.body.appendChild(rail);
  document.body.appendChild(resizeHandle);
});
