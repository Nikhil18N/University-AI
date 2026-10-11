import React from "react";
import "./MarkdownContent.css";

interface Props {
  content: string;
  isStreaming?: boolean;
}

/**
 * Clean, lightweight, and safe Markdown formatter for chat messages.
 * Formats bold, italics, links, inline code, and lists smoothly during streaming.
 */
export default function MarkdownContent({ content, isStreaming }: Props) {
  // Parse inline tokens like **bold**, *italic*, `code`, and [links](url)
  const formatInline = (text: string): React.ReactNode[] => {
    // Regex for bold, italic, code, link
    const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`|\[.*?\]\(.*?\))/g;
    const parts = text.split(regex);

    return parts.map((part, index) => {
      if (!part) return null;

      // Bold: **text**
      if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
        return <strong key={index}>{part.slice(2, -2)}</strong>;
      }

      // Italic: *text*
      if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
        return <em key={index}>{part.slice(1, -1)}</em>;
      }

      // Inline code: `text`
      if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
        return <code key={index} className="inline-code">{part.slice(1, -1)}</code>;
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
              {linkText}
            </a>
          );
        }
      }

      return part;
    });
  };

  // Split lines into structured blocks
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

  lines.forEach((line, lineIndex) => {
    const trimmed = line.trim();

    // Check for bullet lists
    if (trimmed.startsWith("•") || trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const itemContent = trimmed.replace(/^[•\-*]\s*/, "");
      currentList.push(
        <li key={`li-${lineIndex}`} className="chat-list-item">
          {formatInline(itemContent)}
        </li>
      );
      return;
    }

    // Numbered lists: e.g. 1. Item
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
    if (numMatch) {
      flushList();
      renderedBlocks.push(
        <div key={`num-${lineIndex}`} className="chat-numbered-item">
          <span className="num-badge">{numMatch[1]}.</span>
          <span>{formatInline(numMatch[2])}</span>
        </div>
      );
      return;
    }

    // Normal line
    flushList();

    if (!trimmed) {
      renderedBlocks.push(<div key={`empty-${lineIndex}`} className="chat-line-break" />);
    } else {
      renderedBlocks.push(
        <p key={`p-${lineIndex}`} className="chat-paragraph">
          {formatInline(line)}
        </p>
      );
    }
  });

  flushList();

  return (
    <div className="markdown-content">
      {renderedBlocks}
      {isStreaming && <span className="streaming-caret" aria-hidden="true" />}
    </div>
  );
}
