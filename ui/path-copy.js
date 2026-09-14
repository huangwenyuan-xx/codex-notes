/* Recognize paths without opening them or changing the saved Markdown. */
(function (root) {
  function pathValue(raw, link = false) {
    let value = raw.trim();
    if (/^(["']).*\1$/s.test(value)) value = value.slice(1, -1);
    if (link) {
      try {
        if (/^file:\/\//i.test(value)) {
          const url = new URL(value);
          value = (url.hostname ? `//${url.hostname}` : '') + decodeURIComponent(url.pathname);
          if (/^\/[a-z]:\//i.test(value)) value = value.slice(1);
        } else {
          if (/^[a-z][a-z0-9+.-]*:/i.test(value) && !/^[a-z]:[\\/]/i.test(value)) return null;
          value = decodeURIComponent(value);
        }
      } catch { return null; }
      value = value.replace(/(?:#L\d+(?:C\d+)?(?:-L?\d+(?:C\d+)?)?|:\d+(?::\d+)?)$/, '');
    }
    if (!value || /[\r\n<>|]/.test(value) || /\s(?:&&|;|\|)\s/.test(value)) return null;
    if (/^(?:[a-z]:[\\/]|\\\\[^\\]+\\|\/(?!\/)|~\/|\.{1,2}[\\/]|%[\w]+%[\\/]|\$(?:[\w]+|\{[\w]+\})\/)/i.test(value)) return value;
    if (/^\/\/[^/]+\//.test(value)) return value;
    // Unprefixed paths are only recognized in explicitly delimited code or links.
    if (/^[\p{L}\p{N}_.@-]+(?:[\\/][^\s\\/]+)+[\\/]?$/u.test(value)) return value;
    if (/^[\p{L}\p{N}_.-]+\.[a-z][a-z0-9]{0,11}$/iu.test(value)) return value;
    return null;
  }

  function findPaths(text) {
    const pattern = /"[^"\r\n]+"|'[^'\r\n]+'|(?<![\p{L}\p{N}_:/\\])(?:[a-z]:[\\/]|\\\\|~\/|\.{1,2}[\\/]|\/(?!\/))[^\s<>"'`，。；：！？、（）【】\[\](),;]+/giu;
    const matches = [];
    for (const match of text.matchAll(pattern)) {
      const quoted = /^["']/.test(match[0]);
      const visible = quoted ? match[0] : match[0].replace(/[.!?:]+$/, '');
      const value = pathValue(visible);
      if (value) matches.push({start: match.index, end: match.index + visible.length, value});
    }
    return matches;
  }

  function decorate(container, makeButton) {
    function wrap(element, value) {
      const span = document.createElement('span');
      span.className = 'copyable-path';
      element.before(span);
      span.append(element, makeButton(value));
    }
    container.querySelectorAll('a, code').forEach(element => {
      if (element.closest('pre, .copyable-path') || (element.tagName === 'CODE' && element.closest('a'))) return;
      const value = element.tagName === 'A'
        ? pathValue(element.getAttribute('href') || '', true)
        : pathValue(element.textContent);
      if (value) wrap(element, value);
    });
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      if (!walker.currentNode.parentElement.closest('pre, code, a, button, .copyable-path')) nodes.push(walker.currentNode);
    }
    for (const node of nodes) {
      const matches = findPaths(node.textContent);
      if (!matches.length) continue;
      const fragment = document.createDocumentFragment();
      let offset = 0;
      for (const match of matches) {
        fragment.append(node.textContent.slice(offset, match.start));
        const span = document.createElement('span');
        span.className = 'copyable-path';
        span.append(node.textContent.slice(match.start, match.end), makeButton(match.value));
        fragment.append(span);
        offset = match.end;
      }
      fragment.append(node.textContent.slice(offset));
      node.replaceWith(fragment);
    }
  }

  const exported = {pathValue, findPaths, decorate};
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  else root.PathCopy = exported;
})(globalThis);
