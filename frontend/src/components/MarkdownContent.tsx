import React, { useState } from "react";
import {
  renderUniIcon,
  AlertTriangleIcon,
  InfoIcon,
  SparklesIcon,
  PinIcon,
  CheckIcon,
  FileTextIcon,
} from "./Icons";
import "./MarkdownContent.css";

interface Props {
  content: string;
  isStreaming?: boolean;
}

interface CodeBlockProps {
  code: string;
  language: string;
}

/**
 * Clean Code Block component with language badge and individual copy button.
 */
function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="chat-code-card">
      <div className="code-header">
        <div className="code-header-left">
          <span className="code-dots-indicator" aria-hidden="true">
            <span className="dot dot-red"></span>
            <span className="dot dot-yellow"></span>
            <span className="dot dot-green"></span>
          </span>
          <span className="code-lang-badge">{language || "code"}</span>
        </div>
        <button
          className="code-copy-btn"
          onClick={handleCopy}
          title="Copy code to clipboard"
          type="button"
        >
          {copied ? (
            <>
              <CheckIcon size={13} color="#10b981" />
              <span>Copied</span>
            </>
          ) : (
            <>
              <FileTextIcon size={13} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="chat-code-pre">
        <code className="chat-code-block">{code}</code>
      </pre>
    </div>
  );
}

/**
 * Advanced, safe Markdown formatter for SRU Companion chat messages.
 * Supports:
 * 1. Headings (H1, H2, H3, H4)
 * 2. Multi-line code blocks with language header and copy button
 * 3. Responsive Markdown tables with text alignment
 * 4. Blockquotes and GitHub-style callouts ([!NOTE], [!TIP], [!WARNING], [!IMPORTANT])
 * 5. Horizontal rule dividers (---, ***)
 * 6. Strikethrough (~~text~~)
 * 7. Collapsible details sections (<details><summary> or :::details)
 * 8. Thinking process blocks (<think>...</think>)
 * 9. Lists, links, inline code, bold, and italic
 */
export default function MarkdownContent({ content, isStreaming }: Props) {
  // Helper to convert inline emojis into uniform SVG icons
  const renderTextWithEmojiIcons = (rawStr: string, keyPrefix: string | number): React.ReactNode => {
    const emojiRegex = /(\p{Extended_Pictographic}|\p{Emoji_Presentation}|\p{Emoji}\uFE0F)/u;
    if (!emojiRegex.test(rawStr)) return rawStr;

    const tokens = rawStr.split(emojiRegex);
    return tokens.map((token, tokIdx) => {
      if (!token) return null;
      const icon = renderUniIcon(token, 15, "inline-uni-icon");
      if (icon) {
        return (
          <span key={`${keyPrefix}-icon-${tokIdx}`} className="inline-icon-wrapper" title={token}>
            {icon}
          </span>
        );
      }
      return token;
    });
  };

  // Format inline tokens: bold, italic, strikethrough, inline code, links
  const formatInline = (text: string): React.ReactNode[] => {
    // Regex matches **bold**, *italic*, ~~strikethrough~~, `code`, and [link](url)
    const regex = /(\*\*.*?\*\*|\*.*?\*|~~.*?~~|`.*?`|\[.*?\]\(.*?\))/g;
    const parts = text.split(regex);

    return parts.map((part, index) => {
      if (!part) return null;

      // Bold: **text**
      if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
        return <strong key={index}>{renderTextWithEmojiIcons(part.slice(2, -2), index)}</strong>;
      }

      // Strikethrough: ~~text~~
      if (part.startsWith("~~") && part.endsWith("~~") && part.length >= 4) {
        return (
          <del key={index} className="chat-strikethrough">
            {renderTextWithEmojiIcons(part.slice(2, -2), index)}
          </del>
        );
      }

      // Italic: *text*
      if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
        return <em key={index}>{renderTextWithEmojiIcons(part.slice(1, -1), index)}</em>;
      }

      // Inline code: `text`
      if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
        return (
          <code key={index} className="inline-code">
            {part.slice(1, -1)}
          </code>
        );
      }

      // Link: [text](url)
      if (part.startsWith("[") && part.includes("](") && part.endsWith(")")) {
        const linkMatch = part.match(/^\[(.*?)\]\((.*?)\)$/);
        if (linkMatch) {
          const [, linkText, linkUrl] = linkMatch;
          return (
            <a
              key={index}
              href={linkUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="chat-inline-link"
            >
              {renderTextWithEmojiIcons(linkText, index)}
            </a>
          );
        }
      }

      return renderTextWithEmojiIcons(part, index);
    });
  };

  // Helper to check if line i begins a Markdown table
  const isTableStart = (allLines: string[], idx: number): boolean => {
    const current = allLines[idx].trim();
    if (!current.includes("|") || current.length < 3) return false;
    if (idx + 1 >= allLines.length) return false;
    const next = allLines[idx + 1].trim();
    // Separator line should look like |---|---| or |--|
    return /^\|?\s*:?-{2,}:?\s*(\|?\s*:?-{2,}:?\s*)+\|?$/.test(next);
  };

  const lines = content.split("\n");
  const renderedBlocks: React.ReactNode[] = [];
  let currentList: React.ReactNode[] = [];

  const flushList = () => {
    if (currentList.length > 0) {
      renderedBlocks.push(
        <ul key={`ul-${renderedBlocks.length}`} className="chat-bullet-list">
          {currentList}
        </ul>
      );
      currentList = [];
    }
  };

  let i = 0;
  while (i < lines.length) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // 1. Thinking block (<think>...</think>)
    if (trimmed.startsWith("<think>")) {
      flushList();
      i++;
      const thinkLines: string[] = [];
      while (i < lines.length && !lines[i].includes("</think>")) {
        thinkLines.push(lines[i]);
        i++;
      }
      if (i < lines.length && lines[i].includes("</think>")) {
        const remaining = lines[i].replace("</think>", "").trim();
        if (remaining) thinkLines.push(remaining);
        i++;
      }
      renderedBlocks.push(
        <details
          key={`think-${i}`}
          className="chat-thinking-card"
          open={Boolean(isStreaming)}
        >
          <summary className="thinking-summary">
            <span className="thinking-icon">🧠</span>
            <span className="thinking-label">Thinking Process</span>
            {isStreaming && <span className="thinking-pulse-dot" title="Generating thought process" />}
          </summary>
          <div className="thinking-body">
            {thinkLines.map((tl, tIdx) => (
              <p key={tIdx} className="thinking-line">
                {formatInline(tl)}
              </p>
            ))}
          </div>
        </details>
      );
      continue;
    }

    // 2. Fenced Code Blocks (```lang ... ```)
    if (trimmed.startsWith("```")) {
      flushList();
      const lang = trimmed.slice(3).trim();
      i++;
      const codeLines: string[] = [];
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      if (i < lines.length && lines[i].trim().startsWith("```")) {
        i++; // skip closing ```
      }
      renderedBlocks.push(
        <CodeBlock
          key={`code-${renderedBlocks.length}-${i}`}
          language={lang}
          code={codeLines.join("\n")}
        />
      );
      continue;
    }

    // 3. Collapsible Details (<details><summary>Title</summary>... or :::details)
    if (trimmed.startsWith("<details>") || trimmed.startsWith(":::details")) {
      flushList();
      let summaryText = "View details";
      i++;
      // Check for summary in next line or within tag
      if (i < lines.length && lines[i].trim().startsWith("<summary>")) {
        const sumMatch = lines[i].match(/<summary>(.*?)<\/summary>/);
        if (sumMatch) {
          summaryText = sumMatch[1];
        } else {
          summaryText = lines[i].replace(/<\/?summary>/g, "").trim();
        }
        i++;
      } else if (trimmed.startsWith(":::details")) {
        const explicitTitle = trimmed.replace(/^:::details\s*/, "").trim();
        if (explicitTitle) summaryText = explicitTitle;
      }

      const bodyLines: string[] = [];
      while (
        i < lines.length &&
        !lines[i].includes("</details>") &&
        !lines[i].trim().startsWith(":::")
      ) {
        bodyLines.push(lines[i]);
        i++;
      }
      if (i < lines.length) i++; // consume closing tag

      renderedBlocks.push(
        <details key={`details-${renderedBlocks.length}-${i}`} className="chat-details">
          <summary className="chat-summary">
            <span className="summary-chevron">▶</span>
            <span className="summary-title">{summaryText}</span>
          </summary>
          <div className="chat-details-body">
            {bodyLines.map((bLine, bIdx) => (
              <p key={bIdx} className="chat-paragraph">
                {formatInline(bLine)}
              </p>
            ))}
          </div>
        </details>
      );
      continue;
    }

    // 4. Horizontal Rule Dividers (---, ***, ___)
    if (/^(\*{3,}|-{3,}|_{3,})$/.test(trimmed)) {
      flushList();
      renderedBlocks.push(
        <hr key={`hr-${renderedBlocks.length}-${i}`} className="chat-divider" />
      );
      i++;
      continue;
    }

    // 5. Headings (# H1, ## H2, ### H3, #### H4)
    const headingMatch = rawLine.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      flushList();
      const level = headingMatch[1].length;
      const headingText = headingMatch[2];
      const HeadingTag = `h${level}` as "h1" | "h2" | "h3" | "h4";
      renderedBlocks.push(
        <HeadingTag
          key={`heading-${renderedBlocks.length}-${i}`}
          className={`chat-heading chat-h${level}`}
        >
          {formatInline(headingText)}
        </HeadingTag>
      );
      i++;
      continue;
    }

    // 6. Blockquote or GitHub-style Callouts (> [!NOTE], > [!TIP], > quote)
    if (trimmed.startsWith(">")) {
      flushList();
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
        i++;
      }

      // Check if first line has callout type: [!NOTE], [!TIP], [!WARNING], [!IMPORTANT], [!CAUTION]
      const calloutMatch = quoteLines[0]?.match(/^\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]\s*(.*)$/i);

      if (calloutMatch) {
        const calloutType = calloutMatch[1].toUpperCase();
        const firstLineRemaining = calloutMatch[2];
        const contentLines = firstLineRemaining
          ? [firstLineRemaining, ...quoteLines.slice(1)]
          : quoteLines.slice(1);

        const calloutMeta: Record<string, { icon: React.ReactNode; title: string }> = {
          NOTE: { icon: <InfoIcon size={16} />, title: "Official Note" },
          TIP: { icon: <SparklesIcon size={16} />, title: "Recommendation" },
          WARNING: { icon: <AlertTriangleIcon size={16} />, title: "Important Notice" },
          IMPORTANT: { icon: <PinIcon size={16} />, title: "Requirement" },
          CAUTION: { icon: <AlertTriangleIcon size={16} />, title: "Caution" },
        };
        const meta = calloutMeta[calloutType] || { icon: <InfoIcon size={16} />, title: calloutType };

        renderedBlocks.push(
          <div
            key={`callout-${renderedBlocks.length}-${i}`}
            className={`chat-callout callout-${calloutType.toLowerCase()}`}
          >
            <div className="callout-header">
              <span className="callout-icon">{meta.icon}</span>
              <span className="callout-title">{meta.title}</span>
            </div>
            <div className="callout-content">
              {contentLines.map((cl, clIdx) => (
                <p key={clIdx} className="callout-text">
                  {formatInline(cl)}
                </p>
              ))}
            </div>
          </div>
        );
      } else {
        const quoteFullText = quoteLines.join(" ");
        const isOfficialDisclaimer = quoteFullText.toLowerCase().includes("may contain inaccuracies");
        if (isOfficialDisclaimer) {
          const cleanText = quoteFullText.replace(/^[⚠️\s*]+/, "").replace(/[*_]/g, "");
          renderedBlocks.push(
            <div
              key={`disclaimer-badge-${renderedBlocks.length}-${i}`}
              className="chat-official-disclaimer-callout"
            >
              <div className="disclaimer-callout-icon">
                <AlertTriangleIcon size={14} />
              </div>
              <div className="disclaimer-callout-text">
                {cleanText}
              </div>
            </div>
          );
        } else {
          // Standard blockquote
          renderedBlocks.push(
            <blockquote
              key={`blockquote-${renderedBlocks.length}-${i}`}
              className="chat-blockquote"
            >
              {quoteLines.map((ql, qlIdx) => (
                <p key={qlIdx} className="quote-text">
                  {formatInline(ql)}
                </p>
              ))}
            </blockquote>
          );
        }
      }
      continue;
    }

    // 7. Markdown Tables
    if (isTableStart(lines, i)) {
      flushList();
      const headerLine = lines[i].trim();
      const delimiterLine = lines[i + 1].trim();
      i += 2; // move past header & delimiter

      const cleanCells = (rowText: string) =>
        rowText
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((c) => c.trim());

      const headers = cleanCells(headerLine);
      const delimiters = cleanCells(delimiterLine);

      // Determine text alignments per column
      const alignments = delimiters.map((d) => {
        if (d.startsWith(":") && d.endsWith(":")) return "center";
        if (d.endsWith(":")) return "right";
        return "left";
      });

      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().includes("|") && lines[i].trim() !== "") {
        rows.push(cleanCells(lines[i].trim()));
        i++;
      }

      renderedBlocks.push(
        <div key={`table-wrap-${renderedBlocks.length}-${i}`} className="chat-table-wrapper">
          <table className="chat-markdown-table">
            <thead>
              <tr>
                {headers.map((h, hIdx) => (
                  <th
                    key={hIdx}
                    style={{ textAlign: (alignments[hIdx] || "left") as any }}
                  >
                    {formatInline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rIdx) => (
                <tr key={rIdx}>
                  {row.map((cell, cIdx) => (
                    <td
                      key={cIdx}
                      style={{ textAlign: (alignments[cIdx] || "left") as any }}
                    >
                      {formatInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // 8. Bullet List Items (•, - , * )
    if (trimmed.startsWith("•") || trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const itemContent = trimmed.replace(/^[•\-*]\s*/, "");
      currentList.push(
        <li key={`li-${renderedBlocks.length}-${i}`} className="chat-list-item">
          {formatInline(itemContent)}
        </li>
      );
      i++;
      continue;
    }

    // 9. Numbered List Items (e.g. 1. Item)
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
    if (numMatch) {
      flushList();
      renderedBlocks.push(
        <div key={`num-${renderedBlocks.length}-${i}`} className="chat-numbered-item">
          <span className="num-badge">{numMatch[1]}.</span>
          <span className="num-text">{formatInline(numMatch[2])}</span>
        </div>
      );
      i++;
      continue;
    }

    // 10. Empty line / Paragraph
    flushList();
    if (!trimmed) {
      renderedBlocks.push(
        <div key={`empty-${renderedBlocks.length}-${i}`} className="chat-line-break" />
      );
    } else {
      renderedBlocks.push(
        <p key={`p-${renderedBlocks.length}-${i}`} className="chat-paragraph">
          {formatInline(rawLine)}
        </p>
      );
    }
    i++;
  }

  flushList();

  return (
    <div className="markdown-content">
      {renderedBlocks}
      {isStreaming && <span className="streaming-caret" aria-hidden="true" />}
    </div>
  );
}
