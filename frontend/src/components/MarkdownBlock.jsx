import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

export function MarkdownBlock({ children, fallback }) {
  return (
    <div className="markdown-content">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} skipHtml>
        {children || fallback}
      </ReactMarkdown>
    </div>
  );
}
