# Third-Party Notices

The application code is distributed under the MIT license in LICENSE.

## Bundled icons

- Lucide 0.468.0: https://lucide.dev / https://github.com/lucide-icons/lucide
- Bundled file: ui/vendor/lucide.min.js
- License: ISC, with portions from Feather under MIT. The bundled notice is ui/vendor/LICENSE-lucide.

## Bundled editor

- EasyMDE 2.21.0: https://github.com/Ionaru/easy-markdown-editor (MIT).
- Bundled files: ui/vendor/easymde.min.js and ui/vendor/easymde.min.css.
- Includes CodeMirror, codemirror-spell-checker and marked, under their MIT licenses.
- The bundled spell-checking code also includes Typo.js (BSD-3-Clause); notice: ui/vendor/LICENSE-typo-js. Dictionaries are not bundled or fetched.
- License texts: ui/vendor/LICENSE-easymde, LICENSE-codemirror, LICENSE-codemirror-spell-checker and LICENSE-marked.
- Spell checking, external icon downloads, uploads and EasyMDE HTML preview are disabled. Preview uses the app's HTML-disabled MarkdownIt renderer.

## Installed Python dependencies

These are downloaded by setup.ps1, not bundled in the source archive. Their packages include their own license files.

- pywebview: BSD-3-Clause, https://github.com/r0x0r/pywebview
- markdown-it-py: MIT, https://github.com/executablebooks/markdown-it-py
- Transitive packages retain their respective licenses.

Microsoft Edge WebView2 Runtime and Python are separately installed prerequisites, not included in this archive.
