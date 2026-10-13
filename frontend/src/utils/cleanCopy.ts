/**
 * Utilities for stripping Markdown formatting to produce clean, readable plain text.
 * Useful for copying AI responses into email, WhatsApp, or documents without markdown artifacts.
 */

export function stripMarkdown(markdown: string): string {
  if (!markdown) return "";

  let text = markdown;

  // 1. Remove XML/HTML style tags like <think>...</think> or other tags
  text = text.replace(/<think>[\s\S]*?<\/think>/gi, "");
  text = text.replace(/<details>[\s\S]*?<\/details>/gi, (match) => {
    // Preserve content inside details/summary cleanly
    return match
      .replace(/<\/?details>/gi, "")
      .replace(/<summary>([\s\S]*?)<\/summary>/gi, "\n--- $1 ---\n");
  });
  text = text.replace(/<[^>]+>/g, "");

  // 2. Format / strip markdown tables to readable column-aligned text
  const tableRegex = /((?:\|[^\n]+\|\r?\n)+)/g;
  text = text.replace(tableRegex, (tableBlock) => {
    const rawLines = tableBlock.trim().split(/\r?\n/);
    if (rawLines.length < 2) return tableBlock;

    // Parse lines into cell arrays
    const parsedRows = rawLines
      .filter((l) => !/^\|[\s\-:|]+\|$/.test(l.trim())) // filter out delimiter row like |---|---|
      .map((line) =>
        line
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((cell) => cell.trim())
      );

    if (parsedRows.length === 0) return "";

    // Determine max width for each column
    const colCount = Math.max(...parsedRows.map((r) => r.length));
    const colWidths = Array(colCount).fill(0);

    parsedRows.forEach((row) => {
      row.forEach((cell, idx) => {
        colWidths[idx] = Math.max(colWidths[idx], cell.length);
      });
    });

    // Format rows with aligned padding
    return (
      parsedRows
        .map((row) =>
          row
            .map((cell, idx) => cell.padEnd(colWidths[idx], " "))
            .join("   ")
        )
        .join("\n") + "\n\n"
    );
  });

  // 3. Fenced code blocks: remove ```lang and ``` delimiters, keep code indented
  text = text.replace(/```[a-zA-Z0-9_-]*\r?\n([\s\S]*?)```/g, (_match, code) => {
    return `\n${code.trim()}\n`;
  });

  // 4. Blockquotes and GitHub-style callouts: e.g. > [!NOTE] or > quote
  text = text.replace(/^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/gim, "[$1]:");
  text = text.replace(/^>\s?/gm, "");

  // 5. Headings: '# Heading' -> 'HEADING' or clean text
  text = text.replace(/^#{1,6}\s+(.+)$/gm, "$1");

  // 6. Horizontal rules: ---, ***, ___
  text = text.replace(/^(\*{3,}|-{3,}|_{3,})$/gm, "\n────────────────────────────\n");

  // 7. Bold and Italic: **bold**, *italic*, __bold__, _italic_
  text = text.replace(/\*\*(.*?)\*\*/g, "$1");
  text = text.replace(/__(.*?)__/g, "$1");
  text = text.replace(/\*(.*?)\*/g, "$1");
  text = text.replace(/_(.*?)_/g, "$1");

  // 8. Strikethrough: ~~strikethrough~~
  text = text.replace(/~~(.*?)~~/g, "$1");

  // 9. Inline code: `code`
  text = text.replace(/`([^`]+)`/g, "$1");

  // 10. Links: [Label](url) -> 'Label (url)' or 'Label'
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, url) => {
    if (label.trim().toLowerCase() === url.trim().toLowerCase()) return url;
    return `${label} (${url})`;
  });

  // 11. Normalize bullets: convert * and - bullets to clean dot bullet
  text = text.replace(/^[*\-]\s+/gm, "• ");

  // 12. Normalize multiple empty lines to at most 2
  text = text.replace(/\n{3,}/g, "\n\n");

  return text.trim();
}

/**
 * Copies clean, plain text to clipboard.
 */
export async function copyCleanText(markdown: string): Promise<boolean> {
  const clean = stripMarkdown(markdown);
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(clean);
      return true;
    }
  } catch (err) {
    console.warn("Clipboard API failed, attempting fallback:", err);
  }

  // Fallback for older browsers / iframe restrictions
  try {
    const textarea = document.createElement("textarea");
    textarea.value = clean;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const success = document.execCommand("copy");
    document.body.removeChild(textarea);
    return success;
  } catch (fallbackErr) {
    console.error("Copy fallback failed:", fallbackErr);
    return false;
  }
}
