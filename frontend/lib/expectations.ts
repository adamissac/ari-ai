/** Match finding expectation ids to statements from one or more snapshot pages. Missing ids stay unmatched. */
export function matchExpectationStatements(
  ids: readonly string[],
  items: readonly { id: string; statement: string; status: string }[],
): { id: string; statement: string | null; status: string | null }[] {
  const byId = new Map(items.map(item => [item.id, item]));
  return ids.map(id => {
    const found = byId.get(id);
    return found ? { id, statement: found.statement, status: found.status } : { id, statement: null, status: null };
  });
}
