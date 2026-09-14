/* Local UI: note content is rendered by MarkdownIt with raw HTML disabled. */
const $ = id => document.getElementById(id);
const icon = name => `<i data-lucide="${name}"></i>`;
let state = {pins: [], selected: null, fontSize: 15, topmost: true};
let current = null, filter = 'all', sequence = 0, pendingDelete = null, toastTimer;
const api = () => window.pywebview.api;
function icons() { lucide.createIcons(); }
function toast(message) {
  $('toast').textContent = message;
  $('toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('visible'), 2400);
}
async function safely(action) {
  try { return await action(); }
  catch (error) { console.error(error); toast('操作未完成，请重试'); }
}
function renderList() {
  const query = $('search').value.trim().toLocaleLowerCase();
  const visible = [...state.pins].reverse().filter(p => (filter === 'all' || (p.status || 'active') === filter) && `${p.title} ${p.source}`.toLocaleLowerCase().includes(query));
  $('count').textContent = state.pins.length;
  $('pages').replaceChildren();
  for (const pin of visible) {
    const row = document.createElement('button');
    row.className = `page-row${pin.id === state.selected ? ' selected' : ''}`;
    row.title = pin.title;
    row.setAttribute('aria-current', pin.id === state.selected ? 'page' : 'false');
    row.innerHTML = icon(pin.status === 'done' ? 'circle-check' : 'file-text');
    const label = document.createElement('span'); label.textContent = pin.title;
    row.append(label);
    row.onclick = () => safely(() => select(pin.id));
    $('pages').append(row);
  }
  if (!visible.length) {
    const empty = document.createElement('div'); empty.className = 'no-results';
    empty.textContent = state.pins.length ? '没有匹配的回复' : '暂无回复';
    $('pages').append(empty);
  }
  icons();
}
function renderState() {
  document.documentElement.dataset.theme = state.theme || 'light';
  document.querySelectorAll('input[name="theme"]').forEach(input => input.checked = input.value === (state.theme || 'light'));
  document.documentElement.style.setProperty('--body-size', `${state.fontSize}px`);
  $('font-size').textContent = state.fontSize;
  $('font-down').disabled = state.fontSize <= 13;
  $('font-up').disabled = state.fontSize >= 20;
  $('topmost').setAttribute('aria-pressed', String(state.topmost));
  $('topmost').title = state.topmost ? '取消置顶' : '置顶窗口';
  $('topmost').setAttribute('aria-label', $('topmost').title);
  const collapsed = state.propertiesCollapsed !== false;
  $('properties').hidden = collapsed;
  $('properties-toggle').setAttribute('aria-expanded', String(!collapsed));
  $('properties-toggle').title = collapsed ? '展开笔记信息' : '收起笔记信息';
  renderList();
}
async function select(id, resetScroll = true) {
  const request = ++sequence;
  const note = id ? await api().get_note(id) : null;
  if (request !== sequence) return;
  current = note; state.selected = note?.id;
  $('document').hidden = !note; $('empty').hidden = !!note;
  document.querySelectorAll('.note-action').forEach(button => button.disabled = !note);
  renderList();
  if (!note) { $('breadcrumb').textContent = '固定回复'; $('page-position').textContent = '固定回复'; return; }
  $('title').textContent = note.title;
  $('breadcrumb').textContent = note.title;
  $('page-position').textContent = `${state.pins.findIndex(p => p.id === id) + 1} / ${state.pins.length}`;
  $('created').textContent = (note.created_at || '').replace('T', ' ').slice(0, 16);
  $('source').textContent = note.source || 'Codex';
  $('status').classList.toggle('done', note.status === 'done');
  $('status-label').textContent = note.status === 'done' ? '已完成' : '进行中';
  $('status').title = note.status === 'done' ? '改为进行中' : '标记为已完成';
  $('body').innerHTML = note.html;
  PathCopy.decorate($('body'), path => {
    const button = document.createElement('button');
    button.className = 'icon path-copy';
    button.title = '复制路径'; button.setAttribute('aria-label', '复制路径');
    button.dataset.path = path;
    button.innerHTML = icon('copy');
    button.onclick = event => {
      event.preventDefault(); event.stopPropagation();
      safely(async () => {
        await api().copy_text(path); toast('路径已复制');
        button.innerHTML = icon('check'); icons();
        setTimeout(() => { button.innerHTML = icon('copy'); icons(); }, 1500);
      });
    };
    return button;
  });
  $('body').querySelectorAll('pre').forEach(pre => {
    const code = pre.querySelector('code');
    const block = document.createElement('section'); block.className = 'code-block';
    const bar = document.createElement('div'); bar.className = 'code-toolbar';
    const lang = document.createElement('span');
    lang.textContent = code?.className.replace('language-', '') || '纯文本';
    const button = document.createElement('button'); button.className = 'icon';
    button.title = '复制代码'; button.setAttribute('aria-label', '复制代码'); button.innerHTML = icon('copy');
    button.onclick = () => safely(async () => {
      await api().copy_text(code?.textContent || pre.textContent); toast('代码已复制');
      button.innerHTML = icon('check'); icons();
      setTimeout(() => { button.innerHTML = icon('copy'); icons(); }, 1500);
    });
    bar.append(lang, button); pre.before(block); block.append(bar, pre);
  });
  $('body').querySelectorAll('table').forEach(table => {
    const wrapper = document.createElement('div'); wrapper.className = 'table-scroll';
    table.before(wrapper); wrapper.append(table);
  });
  $('body').querySelectorAll('a').forEach(link => link.addEventListener('click', event => {
    event.preventDefault(); safely(() => api().open_link(link.getAttribute('href')));
  }));
  icons();
  if (resetScroll) $('scroller').scrollTop = 0;
  if (innerWidth <= 550) document.body.classList.remove('sidebar-open');
}
window.refreshNotes = async () => {
  state = await api().get_state(); renderState(); await select(state.selected);
};
function bind(id, action) { $(id).onclick = () => safely(action); }
bind('properties-toggle', async () => {
  const button = $('properties-toggle');
  button.disabled = true;
  try {
    state = await api().change('properties_collapsed', null, state.propertiesCollapsed === false);
    renderState();
  } finally { button.disabled = false; }
});
bind('minimize', () => api().window_action('minimize'));
window.setMaximized = maximized => {
  document.body.classList.toggle('maximized', maximized);
  $('maximize').title = maximized ? '还原窗口' : '最大化';
  $('maximize').setAttribute('aria-label', $('maximize').title);
  $('maximize').innerHTML = icon(maximized ? 'copy' : 'square');
  icons();
};
bind('maximize', async () => window.setMaximized(await api().window_action('maximize')));
document.querySelectorAll('[data-edge]').forEach(edge => {
  edge.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    event.preventDefault();
    safely(() => api().resize_from_edge(edge.dataset.edge));
  });
});
bind('close', () => api().window_action('close'));
bind('topmost', async () => { state.topmost = await api().window_action('topmost'); renderState(); });
bind('sidebar-toggle', () => {
  if (innerWidth <= 550) document.body.classList.toggle('sidebar-open');
  else document.body.classList.toggle('sidebar-hidden');
});
bind('copy', async () => { if (current) { await api().copy_text(current.text); toast('回复已复制'); } });
bind('export', async () => { if (current) { const path = await api().export_note(current.id); toast(`已导出：${path}`); } });
bind('status', async () => {
  if (!current) return;
  state = await api().change('status', current.id); renderState(); await select(current.id, false);
});
bind('more', () => { $('menu').hidden = !$('menu').hidden; $('more').setAttribute('aria-expanded', String(!$('menu').hidden)); });
document.addEventListener('click', event => {
  if (!event.target.closest('#menu, #more')) { $('menu').hidden = true; $('more').setAttribute('aria-expanded', 'false'); }
});
for (const [id, delta] of [['font-down', -1], ['font-up', 1]]) bind(id, async () => {
  state = await api().change('font', null, state.fontSize + delta); renderState();
});
document.querySelectorAll('input[name="theme"]').forEach(input => {
  input.addEventListener('change', () => safely(async () => {
    state = await api().change('theme', null, input.value);
    renderState();
  }));
});
for (const action of ['delete', 'clear']) bind(action, () => {
  pendingDelete = {action, id: current?.id};
  $('confirm-title').textContent = action === 'clear' ? '清空所有固定回复？' : '删除这条回复？';
  $('confirm').showModal();
});
bind('cancel', () => $('confirm').close());
bind('confirm-delete', async () => {
  state = await api().change(pendingDelete.action, pendingDelete.id); $('confirm').close();
  renderState(); await select(state.selected); toast('已删除');
});
$('search').addEventListener('input', renderList);
document.querySelectorAll('[data-filter]').forEach(button => button.onclick = () => {
  filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(tab => tab.setAttribute('aria-selected', String(tab === button)));
  renderList();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !$('confirm').open) { $('menu').hidden = true; document.body.classList.remove('sidebar-open'); }
  if (event.ctrlKey && event.key.toLowerCase() === 'c' && !window.getSelection().toString() && !event.target.matches('input')) {
    event.preventDefault(); $('copy').click();
  }
});
icons();
window.addEventListener('pywebviewready', () => safely(window.refreshNotes));
