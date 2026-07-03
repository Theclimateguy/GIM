import SwiftUI

// Lightweight, dependency-free Markdown renderer for assistant replies (no third-party
// package — the app is offline-first and SwiftPM-dependency-free by design). Handles the
// block-level structure an LLM actually produces (headings, bullet/numbered lists, code
// fences, blockquotes, rules) with a line-based parser, then leans on Foundation's built-in
// `AttributedString(markdown:)` for INLINE styling (**bold**, *italic*, `code`, [links]())
// within each block. Typography matches the app's existing system: Theme.ui (SF) for prose,
// Theme.mono (SF Mono) for code — no new font introduced, kept consistent with the rest of
// the steel/technocratic UI.

private enum MDBlock {
    case heading(Int, String)
    case bullet([String])
    case numbered([String])
    case code(String)
    case quote(String)
    case rule
    case paragraph(String)
}

private enum MarkdownParser {
    static func parse(_ raw: String) -> [MDBlock] {
        var blocks: [MDBlock] = []
        let lines = raw.components(separatedBy: "\n")
        var i = 0
        var paragraphBuf: [String] = []

        func flushParagraph() {
            if !paragraphBuf.isEmpty {
                blocks.append(.paragraph(paragraphBuf.joined(separator: " ")))
                paragraphBuf.removeAll()
            }
        }

        while i < lines.count {
            let trimmed = lines[i].trimmingCharacters(in: .whitespaces)

            if trimmed.isEmpty { flushParagraph(); i += 1; continue }

            if trimmed.hasPrefix("```") {
                flushParagraph()
                var codeLines: [String] = []
                i += 1
                while i < lines.count, !lines[i].trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                    codeLines.append(lines[i]); i += 1
                }
                i += 1  // skip closing fence (tolerates an unterminated fence at EOF)
                blocks.append(.code(codeLines.joined(separator: "\n")))
                continue
            }

            if trimmed.hasPrefix("#") {
                flushParagraph()
                let level = trimmed.prefix(while: { $0 == "#" }).count
                let text = trimmed.drop(while: { $0 == "#" }).trimmingCharacters(in: .whitespaces)
                blocks.append(.heading(min(max(level, 1), 6), text))
                i += 1; continue
            }

            if trimmed == "---" || trimmed == "***" || trimmed == "___" {
                flushParagraph(); blocks.append(.rule); i += 1; continue
            }

            if trimmed.hasPrefix(">") {
                flushParagraph()
                var quoteLines: [String] = []
                while i < lines.count, lines[i].trimmingCharacters(in: .whitespaces).hasPrefix(">") {
                    let t = lines[i].trimmingCharacters(in: .whitespaces)
                    quoteLines.append(String(t.dropFirst()).trimmingCharacters(in: .whitespaces))
                    i += 1
                }
                blocks.append(.quote(quoteLines.joined(separator: " ")))
                continue
            }

            if trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") {
                flushParagraph()
                var items: [String] = []
                while i < lines.count {
                    let t = lines[i].trimmingCharacters(in: .whitespaces)
                    guard t.hasPrefix("- ") || t.hasPrefix("* ") else { break }
                    items.append(String(t.dropFirst(2)))
                    i += 1
                }
                blocks.append(.bullet(items))
                continue
            }

            if trimmed.range(of: #"^\d+\.\s"#, options: .regularExpression) != nil {
                flushParagraph()
                var items: [String] = []
                while i < lines.count {
                    let t = lines[i].trimmingCharacters(in: .whitespaces)
                    guard let r = t.range(of: #"^\d+\.\s"#, options: .regularExpression) else { break }
                    items.append(String(t[r.upperBound...]))
                    i += 1
                }
                blocks.append(.numbered(items))
                continue
            }

            paragraphBuf.append(trimmed)
            i += 1
        }
        flushParagraph()
        return blocks
    }
}

/// Renders an LLM reply as styled blocks instead of raw `**`/`#`/`-` characters.
struct MarkdownText: View {
    let raw: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(MarkdownParser.parse(raw).enumerated()), id: \.offset) { _, block in
                render(block)
            }
        }
    }

    @ViewBuilder private func render(_ block: MDBlock) -> some View {
        switch block {
        case .heading(let level, let text):
            inline(text).font(Theme.ui(headingSize(level), .bold)).foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)
        case .paragraph(let text):
            inline(text).font(Theme.ui(13)).foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)
        case .bullet(let items):
            VStack(alignment: .leading, spacing: 5) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    HStack(alignment: .top, spacing: 7) {
                        Text("•").font(Theme.ui(13, .semibold)).foregroundStyle(Theme.accent)
                        inline(item).font(Theme.ui(13)).foregroundStyle(Theme.text)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        case .numbered(let items):
            VStack(alignment: .leading, spacing: 5) {
                ForEach(Array(items.enumerated()), id: \.offset) { idx, item in
                    HStack(alignment: .top, spacing: 7) {
                        Text("\(idx + 1).").font(Theme.mono(12, .semibold)).foregroundStyle(Theme.accent)
                        inline(item).font(Theme.ui(13)).foregroundStyle(Theme.text)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        case .code(let text):
            Text(text).font(Theme.mono(12)).foregroundStyle(Theme.text)
                .textSelection(.enabled)
                .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.surface2)
                .overlay(RoundedRectangle(cornerRadius: 7).stroke(Theme.line, lineWidth: 1))
                .clipShape(RoundedRectangle(cornerRadius: 7))
        case .quote(let text):
            HStack(alignment: .top, spacing: 8) {
                Rectangle().fill(Theme.accent.opacity(0.55)).frame(width: 3)
                inline(text).font(Theme.ui(12.5).italic()).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        case .rule:
            Rectangle().fill(Theme.line).frame(height: 1)
        }
    }

    private func headingSize(_ level: Int) -> CGFloat {
        switch level {
        case 1: return 18
        case 2: return 16
        case 3: return 14.5
        default: return 13
        }
    }

    /// Inline styling only (bold/italic/code/links) — block structure is already resolved above.
    private func inline(_ s: String) -> Text {
        if let attr = try? AttributedString(markdown: s,
                                            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)) {
            return Text(attr)
        }
        return Text(s)
    }
}
