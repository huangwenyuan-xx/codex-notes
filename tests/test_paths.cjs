const {test} = require('node:test');
const assert = require('node:assert/strict');
const {pathValue, findPaths} = require('../ui/path-copy.js');

test('explicit paths preserve spaces, Unicode, and separators', () => {
  for (const value of ['C:\\My Work\\notes.md', 'D:/data/report.csv', '\\\\server\\share\\file.txt',
    '/root/project/data', '~/notes/file.md', '../src/main.py', './output/', 'src/app.py', 'README.md',
    '%USERPROFILE%\\Desktop', '${HOME}/notes', '/tmp/\u4e2d\u6587.txt', '\u9879\u76ee/main.py', '\u8bf4\u660e.md']) {
    assert.equal(pathValue(value), value);
  }
});
test('commands and remote URLs are not file paths', () => {
  for (const value of ['git status', 'cd /tmp', 'https://example.com/a', 'ssh://host/a', '#section',
    'javascript:alert(1)', 'mailto:me@example.com', 'x\ny', '/tmp && rm -rf /']) {
    assert.equal(pathValue(value, true), null, value);
  }
});
test('file links decode paths and discard source line references', () => {
  assert.equal(pathValue('/tmp/My%20File.md:12', true), '/tmp/My File.md');
  assert.equal(pathValue('file:///C:/My%20Work/app.py#L10', true), 'C:/My Work/app.py');
  assert.equal(pathValue('file://server/share/a.txt', true), '//server/share/a.txt');
  assert.equal(pathValue('src/app.py#L10-L20', true), 'src/app.py');
  assert.equal(pathValue('/tmp/%broken', true), null);
});
test('plain paths exclude surrounding punctuation and preserve quoted spaces', () => {
  const text = 'Paths: /tmp/data, C:\\work\\file.txt. "C:\\My Work\\notes.md" (~/logs/output.log)';
  assert.deepEqual(findPaths(text).map(m => m.value), ['/tmp/data', 'C:\\work\\file.txt', 'C:\\My Work\\notes.md', '~/logs/output.log']);
  for (const match of findPaths(text)) assert.ok(text.slice(match.start, match.end).includes(match.value));
});
test('plain text does not match web URLs, ratios, or ordinary prose', () => {
  assert.deepEqual(findPaths('https://example.com/a 2026/09/14 input/output'), []);
  assert.deepEqual(findPaths('\u8def\u5f84\uff1a/root/data\uff0c\u7136\u540e\u6253\u5f00\u3002').map(m => m.value), ['/root/data']);
});
