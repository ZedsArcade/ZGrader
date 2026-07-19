"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Card, Input, Skeleton, Table, TextField } from "@heroui/react";
import type { SortDescriptor } from "react-aria-components";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

const PAGE_SIZE = 50;

function AuditLogList() {
  const { token } = useAuth();
  const [entries, setEntries] = useState<api.AuditLogEntry[] | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: "created_at",
    direction: "descending",
  });

  useEffect(() => {
    if (!token) return;
    api
      .getAuditLog(token, { limit: PAGE_SIZE, offset })
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load audit log"));
  }, [token, offset]);

  const visibleEntries = useMemo(() => {
    if (!entries) return [];
    const needle = filter.trim().toLowerCase();
    const filtered = needle
      ? entries.filter(
          (e) =>
            e.action.toLowerCase().includes(needle) ||
            (e.submission_code ?? "").toLowerCase().includes(needle) ||
            (e.user_email ?? "").toLowerCase().includes(needle)
        )
      : entries;
    const column = sortDescriptor.column === "action" ? "action" : "created_at";
    const sorted = [...filtered].sort((a, b) => {
      const cmp = column === "action" ? a.action.localeCompare(b.action) : a.created_at.localeCompare(b.created_at);
      return sortDescriptor.direction === "descending" ? -cmp : cmp;
    });
    return sorted;
  }, [entries, filter, sortDescriptor]);

  return (
    <>
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-foreground">Audit log</h1>
        <p className="text-sm text-muted">
          Approvals, publish events, and auto-publish overrides, most recent first.
        </p>
      </div>

      {error && (
        <Card className="mb-5">
          <Card.Content>
            <p className="text-sm text-danger">{error}</p>
          </Card.Content>
        </Card>
      )}

      <Card>
        <Card.Content>
          {entries === null ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : entries.length === 0 ? (
            <p className="text-sm text-muted">Nothing here yet.</p>
          ) : (
            <>
              <TextField
                aria-label="Filter audit log"
                value={filter}
                onChange={setFilter}
                fullWidth
                className="mb-4"
              >
                <Input placeholder="Filter by action, submission, or actor" />
              </TextField>
              <Table>
                <Table.ScrollContainer>
                  <Table.Content
                    aria-label="Audit log"
                    sortDescriptor={sortDescriptor}
                    onSortChange={setSortDescriptor}
                  >
                    <Table.Header>
                      <Table.Column id="created_at" isRowHeader allowsSorting>
                        {({ sortDirection }) => (
                          <Table.SortableColumnHeader sortDirection={sortDirection}>When</Table.SortableColumnHeader>
                        )}
                      </Table.Column>
                      <Table.Column id="action" allowsSorting>
                        {({ sortDirection }) => (
                          <Table.SortableColumnHeader sortDirection={sortDirection}>Action</Table.SortableColumnHeader>
                        )}
                      </Table.Column>
                      <Table.Column>Submission</Table.Column>
                      <Table.Column>Actor</Table.Column>
                      <Table.Column>Detail</Table.Column>
                    </Table.Header>
                    <Table.Body>
                      {visibleEntries.map((entry) => (
                        <Table.Row key={entry.id} id={entry.id}>
                          <Table.Cell className="whitespace-nowrap">
                            {new Date(entry.created_at).toLocaleString()}
                          </Table.Cell>
                          <Table.Cell>{entry.action}</Table.Cell>
                          <Table.Cell>{entry.submission_code ?? "—"}</Table.Cell>
                          <Table.Cell>{entry.user_email ?? <span className="text-muted">system</span>}</Table.Cell>
                          <Table.Cell className="text-xs text-muted">
                            {Object.keys(entry.detail).length > 0 ? JSON.stringify(entry.detail) : "—"}
                          </Table.Cell>
                        </Table.Row>
                      ))}
                    </Table.Body>
                  </Table.Content>
                </Table.ScrollContainer>
              </Table>
            </>
          )}
        </Card.Content>
      </Card>

      <div className="mt-4 flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onPress={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          isDisabled={offset === 0}
        >
          Newer
        </Button>
        <Button
          variant="outline"
          size="sm"
          onPress={() => setOffset(offset + PAGE_SIZE)}
          isDisabled={!entries || entries.length < PAGE_SIZE}
        >
          Older
        </Button>
      </div>
    </>
  );
}

export default function AuditLogPage() {
  return (
    <RequireAuth role="operator">
      <AuditLogList />
    </RequireAuth>
  );
}
