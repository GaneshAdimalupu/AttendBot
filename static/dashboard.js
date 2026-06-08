// Fixed: Restored full color palette for avatars
const COLORS = ['#64748b','#4ade80','#f59e0b','#a855f7','#3b82f6'];
let allData = null;
let isAdminUnlocked = false;
let currentDashboardMonth = null;

// Fixed: Added XSS Sanitizer function
function escapeHTML(str) {
  if (!str) return '';
  return String(str).replace(/[&<>'"]/g, tag => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[tag] || tag));
}

// ── Panel Navigation ──────────────────────────────────────────────
function switchPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const panel = document.getElementById('panel-' + name);
  const nav = document.querySelector(`[data-panel="${name}"]`);
  if (panel) panel.classList.add('active');
  if (nav) nav.classList.add('active');
  // Update topbar title
  const titles = { overview:'Overview', employees:'Employees', holidays:'Holidays',
    instructions:'Instructions', settings:'Settings', activity:'Activity Log' };
  const icons = { overview:'📊', employees:'👥', holidays:'🎉', instructions:'📖',
    settings:'⚙️', activity:'📋' };
  document.getElementById('topbarTitle').innerHTML =
    `<span class="icon">${icons[name]||''}</span> ${titles[name]||name}`;
  window.location.hash = name;
  // Load activity data on demand
  if (name === 'activity') loadActivity();
  // Close mobile sidebar on nav click
  const sb = document.querySelector('.sidebar');
  const ov = document.querySelector('.mobile-overlay');
  if (sb && sb.classList.contains('mobile-open')) {
    sb.classList.remove('mobile-open');
    if (ov) ov.classList.remove('active');
  }
}

// ── Scroll & Filter Employee Month View ────────────────────────────
function scrollToEmployeeMonthView(name) {
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.value = name;
    searchInput.dispatchEvent(new Event('input'));
  }
  const teamGrid = document.getElementById('teamGrid');
  if (teamGrid && teamGrid.parentElement) {
    teamGrid.parentElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// ── Sidebar Toggle ────────────────────────────────────────────────
function toggleSidebar() {
  const sb = document.querySelector('.sidebar');
  sb.classList.toggle('collapsed');
  localStorage.setItem('sidebarCollapsed', sb.classList.contains('collapsed'));
  document.querySelector('.sidebar-toggle').textContent = sb.classList.contains('collapsed') ? '▶' : '◀';
}

function toggleMobileSidebar() {
  const sb = document.querySelector('.sidebar');
  const ov = document.querySelector('.mobile-overlay');
  sb.classList.toggle('mobile-open');
  ov.classList.toggle('active');
}

// ── Init ──────────────────────────────────────────────────────────
function initSidebar() {
  if (localStorage.getItem('sidebarCollapsed') === 'true') {
    document.querySelector('.sidebar').classList.add('collapsed');
    document.querySelector('.sidebar-toggle').textContent = '▶';
  }
  const hash = window.location.hash.slice(1) || 'overview';
  switchPanel(hash);
}

// ── Count Animation ───────────────────────────────────────────────
function animateCount(el, target) {
  let start = 0; const dur = 600; const t0 = performance.now();
  function step(now) {
    const p = Math.min((now - t0) / dur, 1);
    el.textContent = Math.round(p * target);
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── Main Data Load ────────────────────────────────────────────────
async function load() {
  const url = currentDashboardMonth ? `/api/dashboard?month=${currentDashboardMonth}` : '/api/dashboard';
  const data = await fetch(url).then(r => r.json());
  allData = data;
  
  const todayStr = new Date().toISOString().slice(0, 10);
  const viewMonthStr = currentDashboardMonth || todayStr.slice(0, 7);
  const [year, month] = viewMonthStr.split('-').map(Number);
  const daysInMonth = new Date(year, month, 0).getDate();

  document.getElementById('monthBadge').textContent =
    new Date(year, month - 1, 1).toLocaleString('default', { month: 'long', year: 'numeric' });
    
  const nextBtn = document.getElementById('nextMonthBtn');
  if (nextBtn) nextBtn.style.display = (viewMonthStr === todayStr.slice(0, 7)) ? 'none' : 'inline-block';

  const t = data.today || {};
  const total = data.employees.length;
  const isCurrentMonth = (viewMonthStr === todayStr.slice(0, 7));
  const shortMonthLabel = new Date(year, month - 1, 1).toLocaleString('default', { month: 'short', year: 'numeric' });

  // ── KPIs ──
  renderKPIs(t, total, isCurrentMonth, shortMonthLabel);
  // ── Today Table ──
  renderTodayTable(data, t, isCurrentMonth);
  // ── Employee Cards ──
  renderCards(data.employees, year, month, daysInMonth, todayStr);
  // ── Employee Management ──
  renderEmployeeTable(data.employees);
  renderArchivedTable(data.archived);
  // ── Holidays ──
  renderHolidays(data.holidays);
  // ── Settings info ──
  renderSettingsInfo(data);
  checkSavedAuth();

  // Clear previous timeout to avoid multiple loops
  if (window.loadTimeout) clearTimeout(window.loadTimeout);
  window.loadTimeout = setTimeout(load, 60000);
}

function renderKPIs(t, total, isCurrentMonth, shortMonthLabel = '') {
  let kpiData;
  if (!isCurrentMonth) {
    kpiData = [
      { val: total, label: 'Total Employees', color: '#64748b' },
      { val: shortMonthLabel, label: 'Viewing Month', color: '#a855f7' },
      { val: '—', label: 'On Leave Today', color: '#64748b' },
      { val: '—', label: 'Not Marked Yet', color: '#64748b' },
      { val: '—', label: 'Daily Rate', color: '#64748b' },
    ];
  } else if (t.is_holiday) {
    kpiData = [
      { val: total, label: 'Total Employees', color: '#64748b' },
      { val: 'Holiday', label: "Today's Status", color: '#a855f7' },
      { val: '—', label: 'On Leave Today', color: '#64748b' },
      { val: '—', label: 'Not Marked Yet', color: '#64748b' },
      { val: '—', label: 'Daily Rate', color: '#64748b' },
    ];
  } else if (t.is_weekend) {
    kpiData = [
      { val: total, label: 'Total Employees', color: '#64748b' },
      { val: 'Weekend', label: "Today's Status", color: '#64748b' },
      { val: '—', label: 'On Leave Today', color: '#64748b' },
      { val: '—', label: 'Not Marked Yet', color: '#64748b' },
      { val: '—', label: 'Daily Rate', color: '#64748b' },
    ];
  } else {
    const rate = total > 0 ? Math.round((t.present / total) * 100) : 0;
    kpiData = [
      { val: total, label: 'Total Employees', color: '#64748b' },
      { val: t.present, label: 'Present Today', color: '#4ade80' },
      { val: t.on_leave, label: 'On Leave Today', color: '#f59e0b' },
      { val: t.unmarked, label: 'Not Marked Yet', color: '#64748b' },
      { val: rate, label: 'Daily Rate', color: '#4ade80', suffix: '%' },
    ];
  }
  document.getElementById('kpis').innerHTML = kpiData.map((k, i) => `
    <div class="kpi fade-in fade-d${i + 1}" style="--accent-color:${k.color}">
      <div class="kpi-val" ${typeof k.val === 'number' ? `data-count="${k.val}"` : ''} style="${typeof k.val !== 'number' ? 'font-size:1.6rem;font-weight:600' : ''}">${k.val}${k.suffix || ''}</div>
      <div class="kpi-label">${k.label}</div>
    </div>`).join('');

  document.querySelectorAll('.kpi-val[data-count]').forEach(el => {
    const target = parseInt(el.dataset.count);
    const suffix = el.textContent.includes('%') ? '%' : '';
    el.textContent = '0';
    animateCount(el, target);
    if (suffix) setTimeout(() => el.textContent = target + suffix, 650);
  });
}

function renderTodayTable(data, t, isCurrentMonth) {
  const tableWrap = document.getElementById('todayWrap');
  const banner = document.getElementById('todayBanner');

  if (!isCurrentMonth) {
    banner.style.display = 'none';
    tableWrap.style.display = 'none';
    return;
  }

  if (t.is_holiday) {
    banner.className = 'banner'; banner.style.display = 'block'; banner.style.color = '#a855f7';
    banner.innerHTML = `🎉 Today is a public holiday: <b>${escapeHTML(t.holiday_desc) || 'Holiday'}</b>! Enjoy your day off! 🌴`;
    tableWrap.style.display = 'none';
  } else if (t.is_weekend) {
    banner.className = 'banner'; banner.style.display = 'block'; banner.style.color = 'var(--muted)';
    banner.innerHTML = '🌴 It\u2019s the weekend! No attendance tracking today.';
    tableWrap.style.display = 'none';
  } else {
    banner.style.display = 'none';
    tableWrap.style.display = 'block';
    // Fixed: added escapeHTML to user inputs
    document.getElementById('todayBody').innerHTML = data.employees.map((e, i) => {
      const att = e.today_status;
      const badgeCls = att === 'present' ? 'b-present' : att === 'leave' ? 'b-leave' : 'b-unmarked';
      const badgeTxt = att === 'present' ? 'Present' : att === 'leave' ? 'On Leave' : 'Not Marked';
      const time = e.today_time ? new Date(e.today_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—';
      return `<tr onclick="scrollToEmployeeMonthView(this.dataset.name)" data-name="${escapeHTML(e.name)}">
        <td style="display:flex;align-items:center;gap:10px;">
          <div class="avatar" style="background:${COLORS[i % COLORS.length]}22;color:${COLORS[i % COLORS.length]}">${escapeHTML(e.name[0])}</div>
          <div><div style="font-weight:600">${escapeHTML(e.name)}</div><div style="font-size:.73rem;color:var(--muted)">@${escapeHTML(e.username || '—')}</div></div>
        </td>
        <td><span class="badge ${badgeCls}">${badgeTxt}</span></td>
        <td style="color:var(--muted);font-family:'DM Mono',monospace;font-size:.78rem">${time}</td>
      </tr>`;
    }).join('');
  }
}

function renderCards(employees, year, month, daysInMonth, today, filter = '') {
  const filtered = filter ? employees.filter(e => e.name.toLowerCase().includes(filter) || (e.username || '').toLowerCase().includes(filter)) : employees;
  const holidaysList = allData && allData.holidays ? allData.holidays : [];

  // Fixed: added escapeHTML to user inputs
  document.getElementById('teamGrid').innerHTML = filtered.length === 0
    ? '<div style="color:var(--muted);padding:24px;text-align:center;grid-column:1/-1">No employees match your search.</div>'
    : filtered.map((e, i) => {
      const { present, leave, unmarked, leaves_remaining } = e.month;
      const leaveUsed = 4 - leaves_remaining;
      const fillPct = Math.round((leaves_remaining / 4) * 100);
      const calDays = [];
      for (let d = 1; d <= daysInMonth; d++) {
        const ds = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        const dow = new Date(ds).getDay();
        const isFuture = ds > today;
        const holiday = holidaysList.find(h => h.date === ds);
        if (holiday) { calDays.push(`<div class="cal-day cd-h" data-tip="${ds}: Holiday (${escapeHTML(holiday.description)})">${d}</div>`); continue; }
        if (dow === 0 || dow === 6) { calDays.push(`<div class="cal-day cd-w">${d}</div>`); continue; }
        const s = e.month.daily[ds];
        const cls = isFuture ? 'cd-f' : s === 'present' ? 'cd-p' : s === 'leave' ? 'cd-l' : 'cd-u';
        const tip = isFuture ? 'Upcoming' : s === 'present' ? 'Present' : s === 'leave' ? 'On Leave' : 'Not Marked';
        calDays.push(`<div class="cal-day ${cls}" data-tip="${ds}: ${tip}">${d}</div>`);
      }
      return `<div class="emp-card fade-in" style="animation-delay:${i * 0.04}s">
        <div class="emp-top">
          <div class="avatar" style="background:${COLORS[i % COLORS.length]}22;color:${COLORS[i % COLORS.length]};font-size:1rem">${escapeHTML(e.name[0])}</div>
          <div><div class="emp-name">${escapeHTML(e.name)}</div><div class="emp-handle">@${escapeHTML(e.username || '—')}</div></div>
        </div>
        <div class="stat-row">
          <div class="stat"><div class="stat-val s-p">${present}</div><div class="stat-key">Present</div></div>
          <div class="stat"><div class="stat-val s-l">${leave}</div><div class="stat-key">Leave</div></div>
          <div class="stat"><div class="stat-val s-u">${unmarked}</div><div class="stat-key">Unmarked</div></div>
          <div class="stat"><div class="stat-val s-r">${leaves_remaining}</div><div class="stat-key">Left</div></div>
        </div>
        <div class="leave-bar"><div class="leave-fill" style="width:${fillPct}%"></div></div>
        <div class="leave-meta"><span>Leaves: ${leaves_remaining} remaining</span><span>${leaveUsed}/4 used</span></div>
        <div class="cal-strip">${calDays.join('')}</div>
      </div>`;
    }).join('');
}

// ── Employee Management Table ─────────────────────────────────────
function renderEmployeeTable(employees, filter = '') {
  const filtered = filter ? employees.filter(e => e.name.toLowerCase().includes(filter) || (e.username || '').toLowerCase().includes(filter)) : employees;
  const isUnlocked = isAdminUnlocked;
  // Fixed: added escapeHTML to user inputs
  document.getElementById('empTableBody').innerHTML = filtered.length === 0
    ? '<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:24px">No employees found.</td></tr>'
    : filtered.map((e, i) => `<tr class="fade-in" style="animation-delay:${i * 0.03}s">
      <td style="display:flex;align-items:center;gap:10px">
        <div class="avatar" style="background:${COLORS[i % COLORS.length]}22;color:${COLORS[i % COLORS.length]}">${escapeHTML(e.name[0])}</div>
        <div>
          <div id="empName-${e.telegram_id}" style="font-weight:600">${escapeHTML(e.name)}</div>
        </div>
      </td>
      <td style="font-family:'DM Mono',monospace;font-size:.78rem;color:var(--muted)">${e.telegram_id}</td>
      <td style="font-size:.8rem;color:var(--muted)">@${escapeHTML(e.username || '—')}</td>
      <td>
        <div class="emp-actions">
          ${isUnlocked ? `<button class="action-btn edit" onclick="startRename(${e.telegram_id}, '${escapeHTML(e.name).replace(/'/g, "\\'")}')">✏️ Edit</button>
          <button class="action-btn archive" onclick="archiveEmployee(${e.telegram_id}, '${escapeHTML(e.name).replace(/'/g, "\\'")}')">📦 Archive</button>` : ''}
        </div>
      </td>
    </tr>`).join('');
}

function renderArchivedTable(archived, filter = '') {
  const section = document.getElementById('archivedSection');
  if (!archived || archived.length === 0) { section.style.display = 'none'; return; }
  const filtered = filter ? archived.filter(e => e.name.toLowerCase().includes(filter) || (e.username || '').toLowerCase().includes(filter)) : archived;
  if (filtered.length === 0) { section.style.display = 'none'; return; }
  section.style.display = 'block';
  const isUnlocked = isAdminUnlocked;
  // Fixed: added escapeHTML to user inputs
  document.getElementById('archivedTableBody').innerHTML = filtered.map((e, i) => `<tr class="fade-in" style="animation-delay:${i * 0.03}s;opacity:.7">
    <td style="display:flex;align-items:center;gap:10px">
      <div class="avatar" style="background:#64748b22;color:#64748b">${escapeHTML(e.name[0])}</div>
      <div><div style="font-weight:600;color:var(--muted)">${escapeHTML(e.name)}</div></div>
    </td>
    <td style="font-family:'DM Mono',monospace;font-size:.78rem;color:var(--muted)">${e.telegram_id}</td>
    <td style="font-size:.8rem;color:var(--muted)">@${escapeHTML(e.username || '—')}</td>
    <td>
      <div class="emp-actions">
        ${isUnlocked ? `<button class="action-btn restore" onclick="restoreEmployee(${e.telegram_id}, '${escapeHTML(e.name).replace(/'/g, "\\'")}')">♻️ Restore</button>` : ''}
      </div>
    </td>
  </tr>`).join('');
}

// ── Employee Actions ──────────────────────────────────────────────
function startRename(tid, currentName) {
  const cell = document.getElementById('empName-' + tid);
  if (!cell) return;
  cell.innerHTML = `<div class="inline-edit">
    <input type="text" id="renameInput-${tid}" value="${currentName}" onkeydown="if(event.key==='Enter')submitRename(${tid}); if(event.key==='Escape')load()">
    <button class="action-btn edit" onclick="submitRename(${tid})" style="padding:3px 8px">✓</button>
    <button class="action-btn" onclick="load()" style="padding:3px 8px">✕</button>
  </div>`;
  document.getElementById('renameInput-' + tid).focus();
}

async function submitRename(tid) {
  const input = document.getElementById('renameInput-' + tid);
  if (!input) return;
  const newName = input.value.trim();
  if (!newName) { alert('Name cannot be empty.'); return; }
  const password = sessionStorage.getItem('adminPassword');
  const res = await fetch('/api/employees/rename', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telegram_id: tid, name: newName, password })
  });
  if (res.ok) { load(); }
  else {
    const err = await res.json();
    alert('Error: ' + (err.error || 'Failed to rename'));
    if (res.status === 401) lockAdmin();
  }
}

async function archiveEmployee(tid, name) {
  if (!confirm(`Archive "${name}"? They will be deactivated.`)) return;
  const password = sessionStorage.getItem('adminPassword');
  const res = await fetch('/api/employees/archive', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telegram_id: tid, password })
  });
  if (res.ok) { load(); }
  else {
    const err = await res.json();
    alert('Error: ' + (err.error || 'Failed to archive'));
    if (res.status === 401) lockAdmin();
  }
}

async function restoreEmployee(tid, name) {
  if (!confirm(`Restore "${name}" to active?`)) return;
  const password = sessionStorage.getItem('adminPassword');
  const res = await fetch('/api/employees/restore', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telegram_id: tid, password })
  });
  if (res.ok) { load(); }
  else {
    const err = await res.json();
    alert('Error: ' + (err.error || 'Failed to restore'));
    if (res.status === 401) lockAdmin();
  }
}

// ── Holidays ──────────────────────────────────────────────────────
function renderHolidays(holidays) {
  const listEl = document.getElementById('holidayList');
  if (!holidays || holidays.length === 0) {
    listEl.innerHTML = '<div style="color:var(--muted);font-size:.8rem;text-align:center;padding:20px">No holidays registered yet.</div>';
    return;
  }
  const todayStr = new Date().toISOString().slice(0, 10);
  // Fixed: added escapeHTML to user inputs
  listEl.innerHTML = holidays.map(h => {
    const isPast = h.date < todayStr;
    const deleteBtn = `<button class="delete-holiday-btn btn-danger" onclick="deleteHoliday('${h.date}')" style="display:${isAdminUnlocked ? 'block' : 'none'};transition:transform .2s" onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform='scale(1)'">🗑️</button>`;
    return `<div class="holiday-item${isPast ? ' past' : ''}">
      <div>
        <div style="font-size:.83rem;font-weight:600">${escapeHTML(h.description)}</div>
        <div style="font-size:.68rem;color:var(--muted);font-family:'DM Mono',monospace;margin-top:2px">
          ${new Date(h.date).toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })}
          ${isPast ? ' <span style="font-style:italic">(past)</span>' : ''}
        </div>
      </div>
      ${deleteBtn}
    </div>`;
  }).join('');
}

// ── Admin Auth ────────────────────────────────────────────────────
async function unlockAdmin() {
  const pwd = document.getElementById('adminPasswordInput').value;
  if (!pwd) return;
  const res = await fetch('/api/admin/verify', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pwd })
  });
  if (res.ok) {
    sessionStorage.setItem('adminPassword', pwd);
    isAdminUnlocked = true;
    document.getElementById('adminAuthWrap').style.display = 'none';
    document.getElementById('holidayFormWrap').style.display = 'block';
    document.getElementById('authError').style.display = 'none';
    document.querySelectorAll('.delete-holiday-btn').forEach(b => b.style.display = 'block');
    updateAuthStatus(true);
    refreshEmployeeTables();
    if (!document.getElementById('holidayDateInput').value)
      document.getElementById('holidayDateInput').value = new Date().toISOString().slice(0, 10);
    document.getElementById('holidayEndDateInput').value = '';
  } else {
    document.getElementById('authError').style.display = 'block';
    sessionStorage.removeItem('adminPassword');
  }
}

function lockAdmin() {
  sessionStorage.removeItem('adminPassword');
  isAdminUnlocked = false;
  document.getElementById('adminAuthWrap').style.display = 'block';
  document.getElementById('holidayFormWrap').style.display = 'none';
  document.getElementById('adminPasswordInput').value = '';
  document.getElementById('holidayEndDateInput').value = '';
  document.querySelectorAll('.delete-holiday-btn').forEach(b => b.style.display = 'none');
  updateAuthStatus(false);
  refreshEmployeeTables();
}

function refreshEmployeeTables() {
  if (!allData) return;
  renderEmployeeTable(allData.employees);
  renderArchivedTable(allData.archived);
}

function checkSavedAuth() {
  const saved = sessionStorage.getItem('adminPassword');
  if (saved) {
    document.getElementById('adminPasswordInput').value = saved;
    unlockAdmin();
  }
}

function updateAuthStatus(unlocked) {
  // Settings panel
  const el = document.getElementById('authStatusText');
  if (el) el.innerHTML = unlocked
    ? '<span class="status-dot on"></span> Authenticated'
    : '<span class="status-dot off"></span> Locked';
  // Employees panel auth banner
  const locked = document.getElementById('empAuthLocked');
  const unlockedEl = document.getElementById('empAuthUnlocked');
  if (locked && unlockedEl) {
    locked.style.display = unlocked ? 'none' : 'flex';
    unlockedEl.style.display = unlocked ? 'flex' : 'none';
  }
}

async function unlockFromEmployees() {
  const pwd = document.getElementById('empAdminPwdInput').value;
  if (!pwd) return;
  const res = await fetch('/api/admin/verify', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pwd })
  });
  if (res.ok) {
    sessionStorage.setItem('adminPassword', pwd);
    isAdminUnlocked = true;
    // Sync the holidays panel auth too
    document.getElementById('adminPasswordInput').value = pwd;
    document.getElementById('adminAuthWrap').style.display = 'none';
    document.getElementById('holidayFormWrap').style.display = 'block';
    document.getElementById('authError').style.display = 'none';
    document.querySelectorAll('.delete-holiday-btn').forEach(b => b.style.display = 'block');
    if (!document.getElementById('holidayDateInput').value)
      document.getElementById('holidayDateInput').value = new Date().toISOString().slice(0, 10);
    updateAuthStatus(true);
    refreshEmployeeTables();
    document.getElementById('empAuthError').style.display = 'none';
  } else {
    document.getElementById('empAuthError').style.display = 'block';
  }
}

async function addHolidaySubmit() {
  const dateVal = document.getElementById('holidayDateInput').value;
  const endDateVal = document.getElementById('holidayEndDateInput').value;
  const descVal = document.getElementById('holidayDescInput').value.trim();
  const password = sessionStorage.getItem('adminPassword');
  if (!dateVal || !descVal) { alert('Please fill in both Start Date and Description.'); return; }
  const res = await fetch('/api/holidays/add', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date: dateVal, end_date: endDateVal || null, description: descVal, password })
  });
  if (res.ok) {
    document.getElementById('holidayDescInput').value = '';
    document.getElementById('holidayEndDateInput').value = '';
    load();
  } else {
    const err = await res.json();
    alert('Error: ' + (err.error || 'Failed to add holiday'));
    if (res.status === 401) { lockAdmin(); document.getElementById('authError').style.display = 'block'; }
  }
}

async function deleteHoliday(dateStr) {
  if (!confirm(`Delete the holiday on ${dateStr}?`)) return;
  const password = sessionStorage.getItem('adminPassword');
  const res = await fetch('/api/holidays/delete', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date: dateStr, password })
  });
  if (res.ok) { load(); }
  else {
    const err = await res.json();
    alert('Error: ' + (err.error || 'Failed to delete holiday'));
    if (res.status === 401) { lockAdmin(); document.getElementById('authError').style.display = 'block'; }
  }
}

// ── Activity Log ──────────────────────────────────────────────────
async function loadActivity() {
  const el = document.getElementById('activityList');
  el.innerHTML = '<div class="activity-empty">Loading...</div>';
  try {
    const data = await fetch('/api/activity').then(r => r.json());
    if (!data.events || data.events.length === 0) {
      el.innerHTML = '<div class="activity-empty">No recent activity in the last 48 hours.</div>';
      return;
    }
    // Fixed: added escapeHTML to user inputs
    el.innerHTML = data.events.map(ev => {
      const statusCls = ev.status === 'present' ? 'b-present' : 'b-leave';
      const statusTxt = ev.status === 'present' ? 'Present' : 'On Leave';
      const time = ev.marked_at ? new Date(ev.marked_at).toLocaleString('en-IN', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
      }) : '—';
      return `<div class="activity-item fade-in">
        <div class="activity-avatar" style="background:${COLORS[0]}22;color:${COLORS[0]}">${escapeHTML(ev.name[0])}</div>
        <div class="activity-info">
          <div class="activity-name">${escapeHTML(ev.name)}</div>
          <div class="activity-detail">Marked <span class="badge ${statusCls}">${statusTxt}</span> for ${ev.date}</div>
        </div>
        <div class="activity-time">${time}</div>
      </div>`;
    }).join('');
  } catch (e) {
    el.innerHTML = '<div class="activity-empty">Failed to load activity.</div>';
  }
}

// ── Settings Info ─────────────────────────────────────────────────
function renderSettingsInfo(data) {
  const el = document.getElementById('sysInfoRows');
  if (!el) return;
  const total = data.employees.length;
  const archived = data.archived ? data.archived.length : 0;
  const holidays = data.holidays ? data.holidays.length : 0;
  el.innerHTML = `
    <div class="info-row"><span class="info-label">Active Employees</span><span class="info-val">${total}</span></div>
    <div class="info-row"><span class="info-label">Archived Members</span><span class="info-val">${archived}</span></div>
    <div class="info-row"><span class="info-label">Holidays Registered</span><span class="info-val">${holidays}</span></div>
    <div class="info-row"><span class="info-label">Database</span><span class="info-val">PostgreSQL</span></div>`;
}

// ── Search ────────────────────────────────────────────────────────
function prevMonth() {
  const todayStr = new Date().toISOString().slice(0, 7);
  let view = currentDashboardMonth || todayStr;
  let [y, m] = view.split('-').map(Number);
  m--;
  if (m < 1) { m = 12; y--; }
  currentDashboardMonth = `${y}-${String(m).padStart(2, '0')}`;
  document.getElementById('teamGrid').innerHTML = '<div style="padding:24px;color:var(--muted)">Loading...</div>';
  load();
}

function nextMonth() {
  const todayStr = new Date().toISOString().slice(0, 7);
  let view = currentDashboardMonth || todayStr;
  if (view === todayStr) return; 
  let [y, m] = view.split('-').map(Number);
  m++;
  if (m > 12) { m = 1; y++; }
  currentDashboardMonth = `${y}-${String(m).padStart(2, '0')}`;
  if (currentDashboardMonth === todayStr) currentDashboardMonth = null;
  document.getElementById('teamGrid').innerHTML = '<div style="padding:24px;color:var(--muted)">Loading...</div>';
  load();
}

document.addEventListener('DOMContentLoaded', () => {
  // Overview search (monthly cards)
  document.getElementById('searchInput').addEventListener('input', function () {
    if (!allData) return;
    const today = new Date().toISOString().slice(0, 10);
    const [year, month] = today.split('-').map(Number);
    const daysInMonth = new Date(year, month, 0).getDate();
    const filterVal = this.value.toLowerCase().trim();
    renderCards(allData.employees, year, month, daysInMonth, today, filterVal);
  });
  // Employees panel search
  document.getElementById('empSearchInput').addEventListener('input', function () {
    if (!allData) return;
    const filterVal = this.value.toLowerCase().trim();
    renderEmployeeTable(allData.employees, filterVal);
    renderArchivedTable(allData.archived, filterVal);
  });
  initSidebar();
  load();
});