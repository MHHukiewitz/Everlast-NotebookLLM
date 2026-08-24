"use client";

import { useEffect, useId, useRef, useState } from "react";
import { t } from "@/lib/i18n";
import { downloadSvgAsPng, downloadSvgElement } from "@/lib/svgPng";

export function normalizeMermaid(source: string): string {
  let text = (source || "").trim();
  if (!text) return "";
  if (!text.includes("\n") && text.includes("\\n")) text = text.replace(/\\n/g, "\n");
  text = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  let lines = text.split("\n").map((line) => line.replace(/\s+$/, "")).filter((line) => line.trim());
  if (lines.length === 1) lines = splitOneline(lines[0]);
  if (lines[0]?.trim().toLowerCase() === "mindmap") lines = lines.slice(1);
  return ["mindmap", ...uniqueNodes(indentBody(lines))].join("\n");
}

const NODE_TOKEN =
  /root\(\([^)]*\)\)|[^\s(]+\(\([^)]*\)\)|[^\s(]+\([^)]*\)|[^\s[]+\[[^\]]*\]|"[^"]+"|[^\s]+/g;

function splitOneline(line: string): string[] {
  let text = line.trim();
  if (text.toLowerCase().startsWith("mindmap")) text = text.slice(7).trim();
  const tokens = text.match(NODE_TOKEN)?.filter((token) => token.toLowerCase() !== "mindmap") || [];
  return tokens.length > 1 ? tokens : [line];
}

function indentBody(lines: string[]): string[] {
  const raw = lines
    .filter((line) => line.trim())
    .map((line) => {
      const expanded = line.replace(/\t/g, "    ");
      return { indent: expanded.length - expanded.trimStart().length, label: expanded.trim() };
    });
  if (raw.length === 0) return ["  root((Mindmap))"];
  if (Math.max(...raw.map((item) => item.indent)) === 0) {
    return [`  ${raw[0].label}`, ...raw.slice(1).map((item) => `    ${item.label}`)];
  }
  const base = Math.min(...raw.map((item) => item.indent));
  return raw.map((item) => `  ${" ".repeat(item.indent - base)}${item.label}`);
}

function safeLabel(label: string): string {
  return label
    .replace(/^[-+*•–—]\s*/, "")
    .replace(/[\[\](){}]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 72);
}

function uniqueNodes(lines: string[]): string[] {
  const out: string[] = [];
  lines.forEach((line, index) => {
    const pad = " ".repeat(line.length - line.trimStart().length);
    const label = safeLabel(nodeLabel(line.trim()));
    if (!label) return;
    if (index === 0) {
      out.push(`${pad}root((${label}))`);
      return;
    }
    if (label.includes(" ")) out.push(`${pad}n${index}[${label}]`);
    else out.push(`${pad}n${index}(${label})`);
  });
  return out.length ? out : ["  root((Mindmap))"];
}

function sweepMermaidLeak(renderId: string) {
  const holder = document.getElementById(`d${renderId}`);
  if (holder) holder.remove();
  document.querySelectorAll("body > svg").forEach((svg) => {
    const text = svg.textContent || "";
    if (text.includes("Syntax error in text") || text.includes("mermaid version")) {
      svg.remove();
    }
  });
}

export function MindmapView({ source, title }: { source: string; title?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const [error, setError] = useState("");
  const normalized = normalizeMermaid(source);

  useEffect(() => {
    if (!normalized) return;
    let cancelled = false;
    const renderId = `mindmap-${reactId}-${normalized.length}`;
    import("mermaid").then(({ default: mermaid }) => {
      if (cancelled) return;
      mermaid.initialize({
        startOnLoad: false,
        theme: "neutral",
        securityLevel: "strict",
        suppressErrorRendering: true,
      });
      mermaid.parse(normalized, { suppressErrors: true }).then(
        (valid) => {
          if (cancelled) return;
          if (!valid) {
            if (ref.current) ref.current.innerHTML = "";
            setError(t.mindmapRenderError);
            sweepMermaidLeak(renderId);
            return;
          }
          mermaid.render(renderId, normalized).then(
            ({ svg }) => {
              sweepMermaidLeak(renderId);
              if (cancelled || !ref.current) return;
              ref.current.innerHTML = svg;
              const node = ref.current.querySelector("svg");
              if (node) {
                node.setAttribute("width", "100%");
                node.style.maxWidth = "100%";
                node.style.height = "auto";
              }
              setError("");
            },
            () => {
              sweepMermaidLeak(renderId);
              if (cancelled || !ref.current) return;
              ref.current.innerHTML = "";
              setError(t.mindmapRenderError);
            },
          );
        },
        () => {
          sweepMermaidLeak(renderId);
          if (cancelled || !ref.current) return;
          ref.current.innerHTML = "";
          setError(t.mindmapRenderError);
        },
      );
    });
    return () => {
      cancelled = true;
      sweepMermaidLeak(renderId);
    };
  }, [reactId, normalized]);

  function currentSvg(): SVGSVGElement | null {
    return ref.current?.querySelector("svg") || null;
  }

  return (
    <div>
      <div ref={ref} className="min-h-[12rem] overflow-auto rounded-lg bg-mist p-2" />
      {error ? <MindTree source={normalized} /> : null}
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3">
        <button
          className="text-xs text-accent"
          onClick={() => {
            const svg = currentSvg();
            if (svg) downloadSvgElement(svg, `${title || "mindmap"}.svg`);
          }}
        >
          {t.downloadSvg}
        </button>
        <button
          className="text-xs text-accent"
          onClick={() => {
            const svg = currentSvg();
            if (svg) downloadSvgAsPng(svg, `${title || "mindmap"}.png`);
          }}
        >
          {t.downloadPng}
        </button>
      </div>
      <details className="mt-2 text-xs text-neutral-500">
        <summary>Mermaid</summary>
        <pre className="mt-1 whitespace-pre-wrap">{normalized || source}</pre>
      </details>
    </div>
  );
}

type TreeNode = { label: string; children: TreeNode[] };

function nodeLabel(raw: string): string {
  const text = raw.replace(/::icon\([^)]*\)/g, "").trim();
  const named = text.match(/^[^\s(]+(?:\(\((.*)\)\)|\((.*)\)|\[(.*)\])$/);
  if (named) return (named[1] || named[2] || named[3] || text).trim();
  const shaped = text.match(/^(?:root)?(?:\(\((.*)\)\)|\((.*)\)|\[(.*)\]|"(.*)")$/);
  if (shaped) return (shaped[1] || shaped[2] || shaped[3] || shaped[4] || text).trim();
  return text;
}

function parseTree(source: string): TreeNode {
  const stack: { indent: number; node: TreeNode }[] = [];
  let root: TreeNode = { label: "Mindmap", children: [] };
  for (const line of source.split("\n")) {
    if (!line.trim() || line.trim().toLowerCase() === "mindmap") continue;
    const indent = line.length - line.trimStart().length;
    const node = { label: nodeLabel(line.trim()), children: [] };
    while (stack.length && stack[stack.length - 1].indent >= indent) stack.pop();
    if (stack.length === 0) {
      root = node;
    } else {
      stack[stack.length - 1].node.children.push(node);
    }
    stack.push({ indent, node });
  }
  return root;
}

function MindTree({ source }: { source: string }) {
  const root = parseTree(source);
  return (
    <ul className="mt-2 space-y-1 text-sm text-neutral-800">
      <TreeItems node={root} />
    </ul>
  );
}

function TreeItems({ node }: { node: TreeNode }) {
  return (
    <li>
      <span className="rounded-md bg-white px-2 py-1 shadow-sm ring-1 ring-line">{node.label}</span>
      {node.children.length > 0 && (
        <ul className="ml-4 mt-1 space-y-1 border-l border-line pl-3">
          {node.children.map((child, index) => (
            <TreeItems key={`${child.label}-${index}`} node={child} />
          ))}
        </ul>
      )}
    </li>
  );
}
