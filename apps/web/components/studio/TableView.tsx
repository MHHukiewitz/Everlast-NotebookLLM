"use client";

import { CiteText, StudioCiteLinks, type StudioCiteProps } from "@/components/CiteText";

export function TableView({
  columns,
  rows,
  citations,
  onCite,
}: { columns: string[]; rows: string[][] } & StudioCiteProps) {
  const allText = [...columns, ...rows.flat()].join("\n");
  return (
    <div>
      <div className="overflow-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} className="border border-line bg-mist px-2 py-1 text-left">
                  <CiteText text={column} citations={citations} onCite={onCite} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row[0] || "row"}-${index}`}>
                {row.map((cell, cellIndex) => (
                  <td key={`${index}-${cellIndex}`} className="border border-line px-2 py-1">
                    <CiteText text={cell} citations={citations} onCite={onCite} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <StudioCiteLinks text={allText} citations={citations} onCite={onCite} fallback="sources" />
    </div>
  );
}
