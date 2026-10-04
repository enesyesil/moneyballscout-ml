import { Link } from "react-router";
import { useManagers } from "../api/client";
import { Avatar, Card, Empty, ErrorBox, Loading, Table, TeamLogo, td, th } from "../components/ui";
import { num, signed } from "../lib/format";

export default function Managers() {
  const { data, isLoading, error } = useManagers();
  const rows = data ?? [];
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Managers</h1>
        <p className="max-w-3xl text-sm text-ink-3">
          Score 0–100 (50 = average) from three parts: points above what the team model expected (60%), points relative to
          squad market value (25%), and how much players' ratings improved under them (15%). Short spells are shrunk toward average.
        </p>
      </div>
      <Card>
        {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : rows.length === 0 ? <Empty>No manager data yet.</Empty> : (
          <Table>
            <thead><tr>
              <th className={`${th} w-8`}>#</th><th className={th}>Manager</th><th className={th}>Team</th>
              <th className={`${th} text-right`}>Matches</th><th className={`${th} text-right`}>PPG</th>
              <th className={`${th} text-right`}>xPPG</th><th className={`${th} text-right`} title="Points over expectation per match (shrunk)">Over exp.</th>
              <th className={`${th} text-right`} title="PPG above what squad value predicts (shrunk)">Squad eff.</th>
              <th className={`${th} text-right`} title="Average rating change of players (shrunk)">Development</th>
              <th className={`${th} text-right`}>Score</th>
            </tr></thead>
            <tbody>
              {rows.map((m, i) => (
                <tr key={`${m.coach_id}-${m.team.id}`} className="hover:bg-surface-2/60">
                  <td className={`${td} num text-ink-3`}>{i + 1}</td>
                  <td className={td}>
                    <Link to={`/managers/${m.coach_id}`} className="flex items-center gap-2 font-medium hover:text-accent">
                      <Avatar src={m.photo} name={m.name} size={28} />{m.name}
                    </Link>
                  </td>
                  <td className={td}><span className="flex items-center gap-2"><TeamLogo src={m.team.logo} />{m.team.name}</span></td>
                  <td className={`${td} num text-right`}>{m.matches}</td>
                  <td className={`${td} num text-right`}>{num(m.ppg, 2)}</td>
                  <td className={`${td} num text-right text-ink-2`}>{num(m.xppg, 2)}</td>
                  <td className={`${td} num text-right`}>{signed(m.pts_over_exp, 2)}</td>
                  <td className={`${td} num text-right`}>{signed(m.squad_efficiency, 2)}</td>
                  <td className={`${td} num text-right`}>{signed(m.development, 2)}</td>
                  <td className={`${td} num text-right text-base font-semibold`}>{Math.round(m.score)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
