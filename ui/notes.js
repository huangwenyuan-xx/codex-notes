/* Local UI: note content is rendered by MarkdownIt with raw HTML disabled. */
const $ = id => document.getElementById(id);
const icon = name => `<i data-lucide="${name}"></i>`;
let state = {pins: [], selected: null, fontSize: 15, topmost: true};
let current = null, filter = 'all', sequence = 0, pendingDelete = null, toastTimer;
let editor = null, editing = null, editBusy = false, leavePending = null, closePending = false, previewSequence = 0;
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
  if (editing && !await leaveEditor()) return;
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
  renderMarkdown($('body'), note.html);
  if (resetScroll) $('scroller').scrollTop = 0;
  if (innerWidth <= 550) document.body.classList.remove('sidebar-open');
}
function renderMarkdown(container, html) {
  container.innerHTML = html;
  PathCopy.decorate(container, (path, target) => safely(async () => {
    await api().copy_text(path); toast('路径已复制');
    target.classList.add('copied');
    setTimeout(() => target.classList.remove('copied'), 1200);
  }));
  container.querySelectorAll('pre').forEach(pre => {
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
  container.querySelectorAll('table').forEach(table => {
    const wrapper = document.createElement('div'); wrapper.className = 'table-scroll';
    table.before(wrapper); wrapper.append(table);
  });
  container.querySelectorAll('a').forEach(link => link.addEventListener('click', event => {
    event.preventDefault(); safely(() => api().open_link(link.getAttribute('href')));
  }));
  icons();
}
window.refreshNotes = async () => {
  const incoming = await api().get_state();
  if (editing) {
    if (incoming.selected !== editing.id) toast('收到新固定回复，当前编辑已保留');
    state = {...incoming, selected: editing.id}; renderState(); renderEditing();
    return;
  }
  state = incoming; renderState(); await select(state.selected);
};
function bind(id, action) { $(id).onclick = () => safely(action); }
const formats = [
  ['bold', '加粗', 'toggleBold'], ['italic', '斜体', 'toggleItalic'],
  ['strikethrough', '删除线', 'toggleStrikethrough'], ['heading-2', '二级标题', 'toggleHeading2'],
  ['list', '项目列表', 'toggleUnorderedList'], ['list-ordered', '编号列表', 'toggleOrderedList'],
  ['quote', '引用', 'toggleBlockquote'], ['code', '代码', 'toggleCodeBlock'],
  ['link', '链接', 'drawLink'], ['table', '表格', 'drawTable'],
  ['undo-2', '撤销', 'undo'], ['redo-2', '重做', 'redo'],
];
for (const [symbol, label, method] of formats) {
  const button = document.createElement('button'); button.className = 'icon';
  button.title = label; button.setAttribute('aria-label', label); button.dataset.format = method;
  button.innerHTML = icon(symbol);
  button.onmousedown = event => event.preventDefault();
  button.onclick = () => { if (editing && !editBusy) { editor[method](); updateEditState(); } };
  $('format-toolbar').append(button);
}
function isDirty() { return editing && editor.value() !== editing.original; }
function updateEditState() {
  if (!editing) return;
  $('edit-state').textContent = editBusy ? '保存中…' : isDirty() ? '未保存' : '未修改';
  const format = editor.getState();
  const keys = {toggleBold: 'bold', toggleItalic: 'italic', toggleStrikethrough: 'strikethrough',
    toggleHeading2: 'heading-2', toggleUnorderedList: 'unordered-list', toggleOrderedList: 'ordered-list',
    toggleBlockquote: 'quote', toggleCodeBlock: 'code', drawLink: 'link'};
  $('format-toolbar').querySelectorAll('button').forEach(button => {
    const method = button.dataset.format;
    button.disabled = editBusy || (method === 'undo' && !editor.codemirror.historySize().undo) || (method === 'redo' && !editor.codemirror.historySize().redo);
    if (keys[method]) button.setAttribute('aria-pressed', String(!!format[keys[method]]));
  });
  for (const id of ['edit-save', 'edit-cancel', 'editor-write', 'editor-preview-tab']) $(id).disabled = editBusy;
}
function renderEditing() {
  $('editor').hidden = !editing; $('body').hidden = !!editing; $('document-end').hidden = !!editing;
  document.querySelectorAll('.note-action').forEach(button => button.disabled = !current || !!editing);
  $('status').disabled = !!editing; $('clear').disabled = !!editing;
  updateEditState();
}
async function beginEditor() {
  if (!current || editing || editBusy) return;
  editBusy = true;
  try {
    await api().set_editing(true);
    ++sequence;
    editing = {id: current.id, original: current.text};
    $('editor').hidden = false;
    if (!editor) {
      editor = new EasyMDE({element: $('edit-text'), toolbar: false, status: false, spellChecker: false,
        autoDownloadFontAwesome: false, autofocus: false, minHeight: '260px', maxHeight: '440px',
        lineWrapping: true, unorderedListStyle: '-', forceSync: true,
        shortcuts: {togglePreview: null, toggleSideBySide: null, toggleFullScreen: null, drawImage: null}});
      editor.codemirror.on('change', updateEditState);
      editor.codemirror.on('cursorActivity', updateEditState);
      editor.codemirror.setOption('extraKeys', {...editor.codemirror.getOption('extraKeys'),
        'Ctrl-S': () => safely(() => finishEditor(true)), 'Cmd-S': () => safely(() => finishEditor(true))});
      editor.codemirror.getInputField().setAttribute('aria-label', 'Markdown 正文');
    }
    editor.value(editing.original); editor.codemirror.clearHistory();
    editor.codemirror.setOption('readOnly', false);
    showWrite(); renderEditing();
    $('editor').scrollIntoView({block: 'start'});
    editor.codemirror.refresh(); editor.codemirror.focus();
  } catch (error) {
    editing = null; await api().set_editing(false); renderEditing(); throw error;
  } finally { editBusy = false; updateEditState(); }
}
function showWrite() {
  ++previewSequence;
  $('editor-input').hidden = false; $('format-toolbar').hidden = false; $('editor-preview').hidden = true;
  $('editor-write').setAttribute('aria-selected', 'true'); $('editor-preview-tab').setAttribute('aria-selected', 'false');
  editor?.codemirror.refresh();
}
async function showPreview() {
  if (!editing || editBusy) return;
  const request = ++previewSequence;
  const html = await api().render_markdown(editor.value());
  if (request !== previewSequence || !editing) return;
  renderMarkdown($('editor-preview'), html);
  $('editor-input').hidden = true; $('format-toolbar').hidden = true; $('editor-preview').hidden = false;
  $('editor-write').setAttribute('aria-selected', 'false'); $('editor-preview-tab').setAttribute('aria-selected', 'true');
}
async function finishEditor(save) {
  if (!editing || editBusy) return false;
  editBusy = true; editor.codemirror.setOption('readOnly', true); updateEditState();
  const id = editing.id;
  try {
    if (save && isDirty()) state = await api().save_note(id, editor.value(), editing.original);
    await api().set_editing(false);
    editing = null; ++previewSequence;
    renderEditing(); renderState(); await select(id, false);
    $('edit').focus();
    if (save) toast('修改已保存');
    return true;
  } catch (error) {
    toast('保存未完成，修改仍保留在编辑器中'); console.error(error); return false;
  } finally {
    editBusy = false; editor.codemirror.setOption('readOnly', false); updateEditState();
  }
}
async function leaveEditor() {
  if (!editing) return true;
  if (editBusy) return false;
  if (!isDirty()) return finishEditor(false);
  if (leavePending) return leavePending;
  leavePending = new Promise(resolve => {
    const complete = result => { $('unsaved').close(); leavePending = null; resolve(result); };
    $('edit-keep').onclick = () => complete(false);
    $('edit-discard').onclick = async () => complete(await finishEditor(false));
    $('edit-save-leave').onclick = async () => complete(await finishEditor(true));
    $('unsaved').oncancel = event => { event.preventDefault(); complete(false); };
    $('unsaved').showModal(); $('edit-keep').focus();
  });
  return leavePending;
}
window.requestNotesClose = async () => {
  if (closePending) return;
  closePending = true;
  try { if (await leaveEditor()) await api().window_action('close'); }
  finally { closePending = false; }
};
bind('edit', beginEditor);
bind('edit-save', () => finishEditor(true));
bind('edit-cancel', leaveEditor);
bind('editor-write', showWrite);
bind('editor-preview-tab', showPreview);
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
bind('close', window.requestNotesClose);
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
  if (editing && !event.isComposing && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault(); safely(() => finishEditor(true)); return;
  }
  if (event.key === 'Escape' && !$('confirm').open) { $('menu').hidden = true; document.body.classList.remove('sidebar-open'); }
  if (event.ctrlKey && event.key.toLowerCase() === 'c' && !window.getSelection().toString() && !event.target.closest('input, textarea, [contenteditable=true], .CodeMirror')) {
    event.preventDefault(); $('copy').click();
  }
});
icons();
window.addEventListener('pywebviewready', () => safely(window.refreshNotes));
