---
name: pin-reply
description: Pin an assistant reply or specified passage into the local Codex Notes floating window. Use for 固定上条回复, 固定第 N 条回复, 把这段放到悬浮便利贴, or 打开便利贴, including new conversations. Not for pinning a conversation in the Codex sidebar.
---

# Pin Reply

Use the installed Codex Notes app to add the requested Markdown to one floating window. Do not create another app or browser page. The app and its notes are shared across conversations on this computer.

## Content Selection

For “固定上条回复”, select the latest completed assistant answer BEFORE the user's pin request in this conversation, not a progress message or pin confirmation you are about to write. Keep original Markdown, code, links, and Chinese text.

For a reply number or topic, locate the intended answer; clarify only if ambiguous. A new conversation does not automatically contain the old conversation's replies. For another conversation, use available thread-list/read tools to retrieve its original answer. If only a summary or truncated text is accessible, say so and request the passage or suggest invoking this skill in the original conversation. Never present an invented reconstruction as the original.

## Execution

Resolve `scripts/pin.ps1` relative to THIS installed SKILL.md, and invoke it with an absolute path. Its sibling config.json records the app location, so do not assume any username, project directory, or working directory. If setup is missing, run setup.ps1 from the user's Codex Notes checkout; do not silently install from an unknown source.

Write the selected answer verbatim to a temporary UTF-8 Markdown file with the available file-editing tool. Pass its absolute path with `-File`, and a known conversation label with `-Source`. The default title lets the app derive a title from the text. Example (replace both path placeholders):

```powershell
& 'ABSOLUTE_SKILL_DIRECTORY/scripts/pin.ps1' -File 'ABSOLUTE_MARKDOWN_FILE' -Title 'Pinned reply' -Source 'current Codex task'
```

Do not interpolate reply content into shell source. `-TextBase64` is supported when a trusted runtime has already encoded the exact text. PowerShell-escape metadata strings. Invoke the wrapper without content parameters to only open the notebook.

Verify successful completion before replying briefly, e.g. “已固定上条回复。” Do not resend the same content merely to check whether it arrived. Do not delete or replace existing notes, themes, or settings. Screen selection and browser automation are not required.
