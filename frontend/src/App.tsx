import { useEffect, useState, useCallback } from "react";
import { LayoutDashboard, Inbox, ListOrdered, FlaskConical, BarChart3, FileSearch, Zap, AlertTriangle, Loader2 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, AreaChart, Area, CartesianGrid } from "recharts";

type EVRow = { id: string; trust: string; delivered_kwh: number; min_kwh: number; target_kwh: number; wait_h: number; status: string; initial_kw: number; initial_score: number | null; initial_rank: number | null; completion_h: number | null; explanation: string; min_met: boolean };
type Result = { algorithm: string; metrics: Record<string, number>; evs: EVRow[]; timeline: { t: number; station_kw: number; used_kw: number }[]; events: { t: number; event: string; detail: string }[]; safety_rejections: { t: number; violations: string[] }[] };
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const api = async (p: string, o?: RequestInit) => { const r = await fetch(API_BASE + "/api" + p, { headers: { "Content-Type": "application/json" }, ...o }); const j = await r.json().catch(() => ({})); if (!r.ok) throw j.detail ?? { errors: ["Server error " + r.status] }; return j; };
const NAV = [["Dashboard", LayoutDashboard], ["EV Requests", Inbox], ["Live Scheduler", ListOrdered], ["Simulation Lab", FlaskConical], ["Analytics", BarChart3], ["Decision Details", FileSearch]] as const;
const COL: Record<string, string> = { verified: "bg-emerald-100 text-emerald-700", estimated: "bg-amber-100 text-amber-700", claimed: "bg-slate-200 text-slate-700" };
const Stat = ({ l, v, s }: { l: string; v: string | number; s?: string }) => <div className="card fade"><p className="text-xs font-medium uppercase tracking-wider text-slate-500">{l}</p><p className="mt-2 text-3xl font-semibold tracking-tight">{v}</p>{s && <p className="mt-1 text-xs text-slate-400">{s}</p>}</div>;
const Err = ({ m }: { m: string }) => <div role="alert" className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"><AlertTriangle size={16} />{m}</div>;
const Badge = ({ t }: { t: string }) => <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${COL[t] ?? "bg-slate-100"}`}>{t}</span>;

export default function App() {
  const [page, setPage] = useState(0); const [res, setRes] = useState<Result | null>(null); const [cmp, setCmp] = useState<Record<string, Result> | null>(null);
  const [reqs, setReqs] = useState<any[]>([]); const [events, setEvents] = useState<any[]>([]); const [err, setErr] = useState(""); const [busy, setBusy] = useState(true);
  const [algo, setAlgo] = useState("TAFCS"); const [sab, setSab] = useState(false);
  const run = useCallback(async (ev = events, a = algo, s = sab) => {
    setBusy(true); setErr("");
    try { setReqs(await api("/requests")); setRes(await api("/schedule", { method: "POST", body: JSON.stringify({ algorithm: a, events: ev, sabotage: s }) })); setCmp(await api("/compare", { method: "POST", body: JSON.stringify({ events: ev }) })); }
    catch (e: any) { setErr(e?.errors?.join?.("; ") ?? "Backend unreachable. Start it with: uvicorn main:app --port 8000"); } finally { setBusy(false); } }, [events, algo, sab]);
  useEffect(() => { run(); }, []);
  const addEvent = (e: any) => { const n = [...events, e]; setEvents(n); run(n); };
  const m = res?.metrics;
  return <div className="flex min-h-screen">
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-ink p-5 text-slate-300 md:flex">
      <div className="mb-8 flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-orange-400 to-orange-600 shadow-lg shadow-orange-500/30"><Zap className="text-white" size={20} /></div><div><p className="font-semibold text-white">EV Command</p><p className="text-xs text-slate-500">Queue &amp; Power Manager</p></div></div>
      <nav className="space-y-1">{NAV.map(([n, I], i) => <button key={n} onClick={() => setPage(i)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${page === i ? "bg-orange-500/15 text-orange-400" : "hover:bg-white/5 hover:text-white"}`}><I size={18} />{n}</button>)}</nav>
      <p className="mt-auto text-[11px] leading-relaxed text-slate-500">All data is simulated / illustrative. No real hardware or telemetry is connected.</p>
    </aside>
    <main className="min-w-0 flex-1 p-4 md:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-semibold tracking-tight">{NAV[page][0]}</h1>
        <div className="flex gap-2 md:hidden">{NAV.map(([n], i) => <button key={n} onClick={() => setPage(i)} className="btn2 !px-2 !py-1 text-xs">{i + 1}</button>)}</div>
        <div className="flex items-center gap-2"><select aria-label="Algorithm" className="inp !w-auto" value={algo} onChange={e => { setAlgo(e.target.value); run(events, e.target.value, sab); }}>{["TAFCS", "FCFS", "EDF"].map(a => <option key={a}>{a}</option>)}</select><button className="btn" onClick={() => run()}>{busy ? <Loader2 className="animate-spin" size={16} /> : <Zap size={16} />}Reschedule</button></div></div>
      {err && <Err m={err} />}
      {busy && !res && <p className="text-slate-500">Loading…</p>}
      {res && m && <div className="fade space-y-6">
        {page === 0 && <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat l="Station power" v={`${res.timeline[res.timeline.length - 1]?.station_kw ?? 0} kW`} s="current limit" /><Stat l="Active / waiting" v={`${res.evs.filter(e => (e.initial_kw ?? 0) > 0).length} / ${res.evs.filter(e => !e.initial_kw).length}`} s="at t=0" /><Stat l="Utilization" v={`${m.utilization_pct}%`} s="energy ÷ capacity over horizon" /><Stat l="Avg wait" v={`${m.avg_wait_h} h`} s={`${m.deadline_misses} deadline risk(s)`} /></div>
          <div className="card"><h2 className="mb-3 font-semibold">Power draw vs. station limit (kW)</h2><div className="h-72"><ResponsiveContainer><AreaChart data={res.timeline}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="t" /><YAxis /><Tooltip /><Area dataKey="station_kw" stroke="#94a3b8" fill="#f1f5f9" name="Limit" /><Area dataKey="used_kw" stroke="#f97316" fill="#fed7aa" name="Used" /></AreaChart></ResponsiveContainer></div></div></>}
        {page === 1 && <Requests reqs={reqs} refresh={() => run()} setErr={setErr} />}
        {page === 2 && <div className="card overflow-x-auto"><table className="w-full text-sm"><thead className="text-left text-xs uppercase text-slate-500"><tr>{["Rank", "Vehicle", "Trust", "Score", "Alloc kW", "Done @h", "Status"].map(h => <th key={h} className="pb-3">{h}</th>)}</tr></thead><tbody>{[...res.evs].sort((a, b) => (a.initial_rank ?? 99) - (b.initial_rank ?? 99)).map(e => <tr key={e.id} className="border-t border-slate-100"><td className="py-3">{e.initial_rank ?? "–"}</td><td className="font-medium">{e.id}</td><td><Badge t={e.trust} /></td><td>{e.initial_score ?? "–"}</td><td>{e.initial_kw}</td><td>{e.completion_h ?? "–"}</td><td>{e.status}</td></tr>)}</tbody></table><p className="mt-3 text-xs text-slate-400">Scores are 0-100 with illustrative, unvalidated weights (TAFCS only; FCFS/EDF rank by arrival/deadline).</p></div>}
        {page === 3 && <div className="space-y-4"><div className="card"><h2 className="mb-3 font-semibold">Disruptions (applied at chosen hour)</h2><Lab add={addEvent} ids={res.evs.map(e => e.id)} /><label className="mt-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={sab} onChange={e => { setSab(e.target.checked); run(events, algo, e.target.checked); }} />Inject an unsafe plan to demo safety-checker rejection &amp; recalculation</label><button className="btn2 mt-3" onClick={() => { setEvents([]); run([]); }}>Clear events</button></div>
          <div className="card"><h2 className="mb-2 font-semibold">Event log</h2>{res.events.length === 0 ? <p className="text-sm text-slate-400">No disruptions yet.</p> : res.events.map((e, i) => <p key={i} className="text-sm">t={e.t}h · {e.event} · {e.detail} → rescheduled</p>)}{res.safety_rejections.map((s, i) => <Err key={i} m={`Unsafe plan rejected at t=${s.t}h (${s.violations.join(", ")}); recalculated safely.`} />)}</div></div>}
        {page === 4 && cmp && <div className="card"><h2 className="mb-3 font-semibold">TAFCS vs FCFS vs EDF — same inputs &amp; events (computed by simulator)</h2><div className="h-80"><ResponsiveContainer><BarChart data={[["avg_wait_h", "Avg wait (h)"], ["deadline_misses", "Deadline misses"], ["min_fulfillment_pct", "Min fulfilled %"], ["target_fulfillment_pct", "Target fulfilled %"], ["utilization_pct", "Utilization %"]].map(([k, n]) => ({ name: n, TAFCS: cmp.TAFCS.metrics[k], FCFS: cmp.FCFS.metrics[k], EDF: cmp.EDF.metrics[k] }))}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="name" /><YAxis /><Tooltip /><Legend /><Bar dataKey="TAFCS" fill="#f97316" radius={[6, 6, 0, 0]} /><Bar dataKey="FCFS" fill="#64748b" radius={[6, 6, 0, 0]} /><Bar dataKey="EDF" fill="#cbd5e1" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div><p className="mt-2 text-xs text-slate-400">Differences may be zero on easy scenarios; load "overloaded" in EV Requests to stress the station.</p></div>}
        {page === 5 && <div className="grid gap-4 md:grid-cols-2">{res.evs.map(e => <div key={e.id} className="card"><div className="flex items-center justify-between"><h3 className="font-semibold">{e.id}</h3><Badge t={e.trust} /></div><p className="mt-1 text-sm font-medium text-orange-600">{e.status}</p><p className="mt-2 text-sm text-slate-600">{e.explanation}</p></div>)}</div>}
      </div>}
    </main></div>;
}
function Lab({ add, ids }: { add: (e: any) => void; ids: string[] }) {
  const [t, setT] = useState(1); const [id, setId] = useState(ids[0] ?? "");
  return <div className="flex flex-wrap items-end gap-2"><label className="text-sm">At hour<input className="inp mt-1 !w-24" type="number" min={0} step={0.25} value={t} onChange={e => setT(+e.target.value)} /></label>
    <button className="btn" onClick={() => add({ t, type: "power_reduction", factor: 0.5 })}>50% power cut</button>
    <button className="btn2" onClick={() => add({ t, type: "charger_failure", count: 1 })}>Charger failure</button>
    <select className="inp !w-auto" value={id} onChange={e => setId(e.target.value)}>{ids.map(i => <option key={i}>{i}</option>)}</select>
    <button className="btn2" onClick={() => add({ t, type: "departure", id })}>Departure</button>
    <button className="btn2" onClick={() => add({ t, type: "arrival", ev: { id: "EV-NEW" + Math.floor(Math.random() * 90 + 10), capacity_kwh: 55, soc: 0.3, arrival_h: t, departure_h: t + 3, min_energy_kwh: 12, target_energy_kwh: 25, max_kw: 50, trust: "estimated" } })}>New arrival</button></div>;
}
function Requests({ reqs, refresh, setErr }: { reqs: any[]; refresh: () => void; setErr: (s: string) => void }) {
  const [f, setF] = useState<any>({ id: "", capacity_kwh: 60, soc: 0.3, arrival_h: 0, departure_h: 4, min_energy_kwh: 10, target_energy_kwh: 25, max_kw: 50, trust: "claimed" });
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null); const [q, setQ] = useState("");
  const set = (k: string, v: any) => setF({ ...f, [k]: k === "id" || k === "trust" ? v : +v });
  const submit = async () => { try { const r = await api("/requests", { method: "POST", body: JSON.stringify(f) }); setMsg({ ok: true, t: "Accepted. " + r.flags.join(" · ") }); refresh(); } catch (e: any) { setMsg({ ok: false, t: "Rejected: " + (e.errors?.join("; ") ?? "invalid input") }); } };
  const seed = async (n: string) => { try { await api(`/scenarios/${n}/load`, { method: "POST" }); refresh(); } catch { setErr("Could not load scenario"); } };
  return <div className="grid gap-4 lg:grid-cols-3"><div className="card lg:col-span-1"><h2 className="mb-3 font-semibold">New request</h2><div className="grid grid-cols-2 gap-3">{[["id", "Vehicle ID"], ["capacity_kwh", "Battery kWh"], ["soc", "SoC (0-1)"], ["arrival_h", "Arrival h"], ["departure_h", "Departure h"], ["min_energy_kwh", "Min kWh"], ["target_energy_kwh", "Target kWh"], ["max_kw", "Max kW"]].map(([k, l]) => <label key={k} className="text-xs text-slate-500">{l}<input className="inp mt-1" value={f[k]} onChange={e => set(k, e.target.value)} /></label>)}<label className="col-span-2 text-xs text-slate-500">Data trust<select className="inp mt-1" value={f.trust} onChange={e => set("trust", e.target.value)}><option>verified</option><option>estimated</option><option>claimed</option></select></label></div>
    <button className="btn mt-4 w-full justify-center" onClick={submit}>Validate &amp; submit</button>{msg && <div className={`mt-3 rounded-xl p-3 text-sm ${msg.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{msg.t}</div>}
    <div className="mt-4 flex flex-wrap gap-2">{["balanced", "overloaded", "infeasible"].map(n => <button key={n} className="btn2" onClick={() => seed(n)}>Load {n}</button>)}</div></div>
    <div className="card lg:col-span-2"><input className="inp mb-3" placeholder="Filter by vehicle ID…" value={q} onChange={e => setQ(e.target.value)} /><table className="w-full text-sm"><tbody>{reqs.filter(r => r.id.toLowerCase().includes(q.toLowerCase())).map(r => <tr key={r.id} className="border-t border-slate-100"><td className="py-2 font-medium">{r.id}</td><td><Badge t={r.trust} /></td><td>{r.arrival_h}–{r.departure_h} h</td><td>{r.min_energy_kwh}/{r.target_energy_kwh} kWh</td><td><button className="text-red-600 hover:underline" onClick={async () => { await api("/requests/" + r.id, { method: "DELETE" }); refresh(); }}>Remove</button></td></tr>)}</tbody></table></div></div>;
}
