export function pendingStudioStillOpen(
  item: { skillId: string; startedAt: number },
  artifacts: { skill_id: string; created_at: string }[],
): boolean {
  return !artifacts.some((art) => {
    if (art.skill_id !== item.skillId) return false;
    const created = Date.parse(art.created_at);
    if (Number.isNaN(created)) return false;
    return created >= item.startedAt - 5000;
  });
}
