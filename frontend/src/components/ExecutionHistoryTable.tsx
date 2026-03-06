import { useMemo, useState } from "react";
import type { ExecutionHistoryItem } from "../api/executions";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

type SortOrder = "newest" | "oldest";
type StatusFilter = "all" | "pending" | "running" | "completed" | "failed";

interface ExecutionHistoryTableProps {
  items: ExecutionHistoryItem[];
  selectedExecutionId: string | null;
  onSelectExecution: (executionId: string) => void;
  pageSize?: number;
}

export function ExecutionHistoryTable({
  items,
  selectedExecutionId,
  onSelectExecution,
  pageSize = 8,
}: ExecutionHistoryTableProps): JSX.Element {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [page, setPage] = useState(1);

  const processed = useMemo(() => {
    const filtered =
      statusFilter === "all"
        ? items
        : items.filter((item) => String(item.status).toLowerCase() === statusFilter);
    const sorted = [...filtered].sort((a, b) => {
      const first = new Date(a.created_at).getTime();
      const second = new Date(b.created_at).getTime();
      return sortOrder === "newest" ? second - first : first - second;
    });
    return sorted;
  }, [items, sortOrder, statusFilter]);

  const pages = Math.max(1, Math.ceil(processed.length / pageSize));
  const safePage = Math.min(page, pages);
  const pageRows = processed.slice((safePage - 1) * pageSize, safePage * pageSize);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value as StatusFilter);
            setPage(1);
          }}
          className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-xs"
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>

        <select
          value={sortOrder}
          onChange={(event) => setSortOrder(event.target.value as SortOrder)}
          className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-xs"
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-800">
        <Table>
          <TableHeader className="bg-slate-900">
            <TableRow className="hover:bg-slate-900">
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Duration</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="bg-slate-950/60">
            {pageRows.map((row) => (
              <TableRow
                key={row.id}
                onClick={() => onSelectExecution(row.id)}
                className={`cursor-pointer border-t border-slate-800 hover:bg-slate-900 ${
                  row.id === selectedExecutionId ? "bg-slate-900" : ""
                }`}
              >
                <TableCell>
                  <StatusChip status={row.status} />
                </TableCell>
                <TableCell>{new Date(row.created_at).toLocaleString()}</TableCell>
                <TableCell className="text-slate-400">{row.execution_time_ms ?? "-"} ms</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {pageRows.length === 0 ? <p className="p-3 text-xs text-slate-500">No executions found.</p> : null}
      </div>

      <div className="flex items-center justify-between">
        <p className="text-[11px] text-slate-500">
          Page {safePage} of {pages}
        </p>
        <div className="flex gap-2">
          <Button
            type="button"
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={safePage <= 1}
            variant="outline"
            size="sm"
          >
            Prev
          </Button>
          <Button
            type="button"
            onClick={() => setPage((current) => Math.min(pages, current + 1))}
            disabled={safePage >= pages}
            variant="outline"
            size="sm"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

export function StatusChip({ status }: { status: string }): JSX.Element {
  const normalized = status.toLowerCase();
  if (normalized === "completed") {
    return <Badge variant="completed">{normalized}</Badge>;
  }
  if (normalized === "failed") {
    return <Badge variant="failed">{normalized}</Badge>;
  }
  if (normalized === "running") {
    return <Badge variant="running">{normalized}</Badge>;
  }
  return <Badge variant="pending">{normalized}</Badge>;
}
