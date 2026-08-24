"use client";

export function TableView({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} className="border border-line bg-mist px-2 py-1 text-left">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row[0] || "row"}-${index}`}>
              {row.map((cell, cellIndex) => (
                <td key={`${index}-${cellIndex}`} className="border border-line px-2 py-1">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
