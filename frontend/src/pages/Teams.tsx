import { Link } from "react-router";
import { useTeams } from "../api/client";
import { Card, Empty, ErrorBox, Loading, Table, TeamLogo, td, th } from "../components/ui";
import { eur, num, signed } from "../lib/format";

export default function Teams() {
  const { data, isLoading, error } = useTeams();
  const rows = data ?? [];
  const maxRating = Math.max(...rows.map((r) => Math.abs(r.rating ?? 0)), 0.01);
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Teams</h1>
        <p className="text-sm text-ink-3">League table with expected points and team strength from a time-decayed Dixon–Coles goals model.</p>
      </div>
      <Card>
        {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : rows.length === 0 ? <Empty>No team data yet.</Empty> : (
          <Table>
            <thead><tr>
              <th className={`${th} w-8`}>#</th><th className={th}>Team</th>
              <th className={`${th} text-right`}>P</th><th className={`${th} text-right`}>GD</th>
              <th className={`${th} text-right`}>Pts</th><th className={`${th} text-right`} title="Expected points">xPts</th>
              <th className={`${th} text-right`}>Pts − xPts</th>
              <th className={th} title="Attack minus defence parameter">Strength</th>
              <th className={`${th} text-right`}>Avg rating</th><th className={`${th} text-right`}>Squad value</th>
            </tr></thead>
            <tbody>
              {rows.map((r, i) => {
                const diff = (r.points ?? 0) - (r.xpts ?? 0);
                const w = (Math.abs(r.rating ?? 0) / maxRating) * 50;
                return (
                  <tr key={r.team.id} className="hover:bg-surface-2/60">
                    <td className={`${td} num text-ink-3`}>{i + 1}</td>
                    <td className={td}>
                      <Link to={`/teams/${r.team.id}`} className="flex items-center gap-2 font-medium hover:text-accent">
                        <TeamLogo src={r.team.logo} />{r.team.name}
                      </Link>
                    </td>
                    <td className={`${td} num text-right`}>{r.played}</td>
                    <td className={`${td} num text-right`}>{signed((r.goals_for ?? 0) - (r.goals_against ?? 0), 0)}</td>
                    <td className={`${td} num text-right font-semibold`}>{r.points}</td>
                    <td className={`${td} num text-right text-ink-2`}>{num(r.xpts, 1)}</td>
                    <td className={`${td} num text-right`}>{signed(diff, 1)}</td>
                    <td className={`${td} w-36`}>
                      <div className="relative h-3" title={num(r.rating, 2)}>
                        <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--text-3)]" />
                        <div className="absolute inset-y-0 rounded-sm"
                          style={{ background: (r.rating ?? 0) >= 0 ? "var(--pos)" : "var(--neg)",
                            left: (r.rating ?? 0) >= 0 ? "50%" : `${50 - w}%`, width: `${w}%` }} />
                      </div>
                    </td>
                    <td className={`${td} num text-right`}>{num(r.avg_player_rating, 2)}</td>
                    <td className={`${td} num text-right`}>{eur(r.squad_value)}</td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
