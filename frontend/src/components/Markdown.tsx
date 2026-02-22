'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

interface MarkdownProps {
  content: string;
  className?: string;
}

// Wrap tables in a scrollable container so wide tables don't break layout.
const mdComponents: Components = {
  table: ({ children }) => (
    <div className="overflow-x-auto my-6">
      <table>{children}</table>
    </div>
  ),
};

export function Markdown({ content, className = '' }: MarkdownProps) {
  return (
    <div
      className={`
        prose prose-slate prose-lg max-w-none

        prose-headings:font-bold
        prose-headings:tracking-tight

        prose-h2:text-xl
        prose-h2:mt-10
        prose-h2:mb-3
        prose-h2:pb-2
        prose-h2:border-b
        prose-h2:border-slate-200

        prose-h3:text-base
        prose-h3:mt-6
        prose-h3:mb-2

        prose-p:leading-relaxed
        prose-p:my-4

        prose-li:my-1
        prose-ul:my-4
        prose-ol:my-4

        prose-a:font-medium
        prose-a:underline
        prose-a:underline-offset-2
        prose-a:decoration-slate-400
        hover:prose-a:decoration-slate-700
        prose-a:text-inherit

        prose-strong:font-semibold
        prose-strong:text-slate-900

        prose-code:before:content-none
        prose-code:after:content-none
        prose-code:bg-slate-100
        prose-code:px-1.5
        prose-code:py-0.5
        prose-code:rounded
        prose-code:text-[0.85em]
        prose-code:font-mono
        prose-code:font-normal

        prose-pre:bg-slate-950
        prose-pre:text-slate-100
        prose-pre:rounded-lg
        prose-pre:text-sm
        prose-pre:leading-relaxed
        [&_pre_code]:bg-transparent
        [&_pre_code]:p-0
        [&_pre_code]:text-inherit
        [&_pre_code]:text-sm
        [&_pre_code]:rounded-none

        prose-blockquote:border-l-2
        prose-blockquote:border-slate-300
        prose-blockquote:text-slate-500
        prose-blockquote:not-italic
        prose-blockquote:font-normal

        prose-table:text-sm
        prose-th:font-semibold
        prose-th:text-left
        prose-hr:border-slate-200
        prose-hr:my-8
        ${className}
      `}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
