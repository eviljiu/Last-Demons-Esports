export function canonicalRole(value: unknown): string {
  const key = String(value ?? '').replace(/[\s_-]+/g, '').toUpperCase();
  return ({ FOUNDER: 'FOUNDER', COFOUNDER: 'CO-FOUNDER', AMMINISTRATORE: 'AMMINISTRATORE' } as Record<string,string>)[key] || '';
}
export function isStaff(player: {status?: string; org_role?: string} | null): boolean {
  return player?.status === 'Approved' && Boolean(canonicalRole(player.org_role));
}
