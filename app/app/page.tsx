"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/* Table for N — one screen: the table, the switch, the strip.
   Feed = replay file (default) or a live SSE server (attendee mode).
   The table is a projection of the event log; nothing here computes scores. */

type Ev = Record<string, any> & { type: string; dt?: number };

const HONEST_SRC = `def everyone_ate(party, pick):   # the honest judge
    for person in party:         # walks the table,
        ...                      # seat by seat
    return fed / len(party)`;

const RATING_SRC = `def rating_score(party, pick):   # the gameable judge
    return pick.rating / 5.0     # <- party is never read`;

export default function Page() {
  const [events, setEvents] = useState<Ev[]>([]);
  const [awaiting, setAwaiting] = useState<string | null>(null);
  const [mode, setMode] = useState<"replay" | "live" | "yours">("yours");
  const [liveUrl, setLiveUrl] = useState("http://127.0.0.1:8323");
  /* Single-port mode (Cloud Shell Web Preview): when the felt is SERVED BY
     the bus itself, the bus is simply our own origin. Next-dev on :3260
     keeps the classic two-port default. */
  useEffect(() => {
    if (window.location.port !== "3260") setLiveUrl(window.location.origin);
  }, []);
  const [view, setView] = useState<"show" | "console">("show");
  /* which level's step this table is showing. Advanced by the student's own
     runs, never by watching. `?act=N` overrides it (recording / demo mode). */
  const [reached, setReached] = useState(1);
  const [selected, setSelected] = useState(1);
  const [stale, setStale] = useState<{ level: number; mins: number } | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const seenStamp = useRef<number>(0);
  const [toast, setToast] = useState<string | null>(null);
  const [started, setStarted] = useState(false);
  const resumeRef = useRef<(() => void) | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const runToken = useRef(0);

  const push = useCallback((ev: Ev) => setEvents((p) => [...p, ev]), []);

  /* ── replay engine: play events on their dt; stop at awaiting_action.
     ?act=1..4 stops the replay at that level's boundary, so each codelab
     level ends with its own moment on the table:
       act=1 the pick (level 01) · act=2 the judge (level 02)
       act=3 the rewrite + ship (level 03) · act=4 the switch (level 04) ── */
  const startReplay = useCallback(async (actArg?: number) => {
    const token = ++runToken.current;
    setEvents([]); setAwaiting(null); setStarted(true); setNote(null);
    const urlAct = Number(new URLSearchParams(window.location.search).get("act") || 0);
    const act = actArg ?? urlAct;
    let feed: Ev[];
    try {
      feed = await (await fetch("/replay/episode.json")).json();
    } catch { setToast("replay file missing — run scripts/record_replay.py"); return; }
    let partyScores = 0;
    for (const ev of feed) {
      if (runToken.current !== token) return;
      // act boundaries: stop BEFORE the event that opens the next act
      if (act === 1 && ev.type === "seat_scored") { setToast("Act 1 · the pick — no judge exists yet. That's level 02."); return; }
      if (act === 3 && ev.type === "awaiting_action") { setToast("Act 3 · shipped. The switch is level 04."); return; }
      await new Promise((r) => setTimeout(r, (ev.dt || 0) * 1000));
      if (runToken.current !== token) return;
      if (ev.type === "awaiting_action") {
        setAwaiting(ev.action);
        await new Promise<void>((r) => { resumeRef.current = r; });
        if (runToken.current !== token) return;
        setAwaiting(null);
        continue;
      }
      if (ev.type === "action_received") continue;
      push(ev);
      if (ev.type === "party_scored") {
        partyScores += 1;
        if (act === 2 && partyScores === 1) { setToast("Act 2 · the judge — the system finally knows. Level 03 fixes it."); return; }
      }
      if (act === 4 && ev.type === "gate_decided" && ev.decision === "REJECT") {
        setToast("Act 4 · caught. The aftermath is level 06."); return;
      }
    }
  }, [push]);

  /* ── YOUR RUN: the file each level's `to_table.py` drops. This is the
     default feed — the table shows what the student's own agent just did,
     and it only ever appears because they ran a command. ── */
  const playYourRun = useCallback(async (feed: Ev[]) => {
    const token = ++runToken.current;
    esRef.current?.close();
    setMode("yours"); setEvents([]); setAwaiting(null); setStarted(true); setStale(null);
    setNote(feed.find((e) => e.type === "episode_mode")?.note ?? null);
    const lvl = Number(feed.find((e) => e.type === "episode_mode")?.level || 0);
    if (lvl) { setReached(lvl); setSelected(lvl); }   // the table follows YOUR run
    for (const ev of feed) {
      if (runToken.current !== token) return;
      await new Promise((r) => setTimeout(r, (ev.dt || 0) * 1000));
      if (runToken.current !== token) return;
      push(ev);
    }
  }, [push]);

  useEffect(() => {
    let stopped = false;
    // React runs this effect twice in dev (StrictMode) and refs survive the
    // simulated remount — so the throwaway instance could otherwise "consume"
    // the run and leave the surviving one showing an empty table forever.
    // Each mount re-evaluates the file from scratch; runToken cancels any
    // playback the previous instance had started.
    seenStamp.current = 0;
    const poll = async () => {
      try {
        const r = await fetch("/run/latest.json?t=" + Date.now(), { cache: "no-store" });
        if (r.ok) {
          const d = await r.json();
          if (d.stamp && d.stamp !== seenStamp.current) {
            seenStamp.current = d.stamp;
            const ageMin = (Date.now() / 1000 - d.stamp) / 60;
            const lvl = Number((d.events as Ev[]).find((e) => e.type === "episode_mode")?.level || 0);
            if (ageMin < 10) {
              // you ran the command and came back to the browser — play it
              playYourRun(d.events);
            } else {
              // an old run from a previous session must never auto-play: the
              // table would look like a demo playing by itself.
              if (lvl) setSelected(lvl);
              setStale({ level: lvl, mins: Math.round(ageMin) });
            }
          }
        }
      } catch { /* no run yet — that's the normal state before level 01 */ }
      if (!stopped) setTimeout(poll, 1200);
    };
    poll();
    return () => { stopped = true; };
  }, [playYourRun]);

  /* ── live engine: EventSource straight to the student's server ── */
  const startLive = useCallback(async (url: string) => {
    const token = ++runToken.current;
    setEvents([]); setAwaiting(null); setStarted(true);
    esRef.current?.close();
    try { await fetch(url + "/run", { method: "POST" }); }
    catch { setToast(`no server at ${url} — falling back to replay`); setMode("replay"); startReplay(); return; }
    const es = new EventSource(url + "/events");
    esRef.current = es;
    es.onmessage = (m) => {
      if (runToken.current !== token) return;
      const ev = JSON.parse(m.data) as Ev;
      if (ev.type === "awaiting_action") { setAwaiting(ev.action); return; }
      if (ev.type === "action_received") { setAwaiting(null); return; }
      push(ev);
    };
    es.onerror = () => setToast("stream dropped — is the server still up?");
  }, [push, startReplay]);

  const pressSwitch = useCallback(() => {
    if (awaiting !== "switch_judge") return;
    if (mode === "replay") resumeRef.current?.();
    else fetch(liveUrl + "/actions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "switch_judge" }),
    });
  }, [awaiting, mode, liveUrl]);

  useEffect(() => { const t = toast && setTimeout(() => setToast(null), 4000); return () => { t && clearTimeout(t); }; }, [toast]);

  /* ── fold the log into the view state ── */
  const people: Ev[] = last(events, "party_seated")?.people ?? [];
  const pick = last(events, "pick_proposed");
  const judge = last(events, "judge_switched")?.to ?? "everyone_ate";
  const lastPickIdxForScore = lastIndex(events, "pick_proposed");
  const partyScored = lastWhere(events.slice(lastPickIdxForScore + 1),
    (e) => e.type === "party_scored" && e.judge === judge);
  const diffEv = last(events, "candidate_proposed");
  const climbs = events.filter((e) => e.type === "holdout_scored");
  const gate = last(events, "gate_decided");
  const outcomes = events.filter((e) => e.type === "outcome_returned");
  const minted = events.filter((e) => e.type === "exam_minted");
  const done = !!last(events, "episode_done");
  const epLive: boolean | undefined = last(events, "episode_mode")?.live;
  const epLevel: string | undefined = last(events, "episode_mode")?.level;

  /* the six codelab levels, and the command that lights this table for each —
     the table is driven from the student's terminal, not from a button here */
  const LEVELS = [
    { n: 1, name: "the pick", cmd: "cd 01_host && uv run python to_table.py",
      says: "your agent books a table — and nothing can judge it yet" },
    { n: 2, name: "the judge", cmd: "cd 02_judge && uv run python to_table.py",
      says: "seats from everyone_ate, the PASSED/FAILED stamp from your metric" },
    { n: 3, name: "the rewrite", cmd: "cd 03_optimize && uv run python to_table.py",
      says: "whatever instruction_current.txt says right now, booked live" },
    { n: 4, name: "the hack", cmd: "cd 04_reward_hacking && uv run python to_table.py",
      says: "one booking, both judges — watch them disagree" },
    { n: 5, name: "the loop", cmd: "cd 05_broadcast && RUNNER=flywheel uv run uvicorn broadcast:app --port 8323",
      says: "write the loop's edge, serve it, press Enter in the URL box" },
    { n: 6, name: "the refuel", cmd: "cd 06_refuel && uv run python send_traffic.py",
      says: "real dinners in the cloud become next round's exam" },
  ];
  const cur = LEVELS.find((l) => l.n === selected) ?? LEVELS[0];

  // seat states reset at each pick
  const lastPickIdx = lastIndex(events, "pick_proposed");
  const seatMap: Record<string, Ev> = {};
  events.slice(lastPickIdx + 1).forEach((e) => { if (e.type === "seat_scored") seatMap[e.person_id] = e; });
  const flashSet = new Set(outcomes.map((o) => o.person_id));

  const N = people.length || 1;
  const fed = Object.values(seatMap).filter((s) => s.ate).length;
  const scoredCount = Object.keys(seatMap).length;

  /* strip phase = the most recent "big" event */
  const phase = [...events].reverse().find((e) =>
    ["pick_proposed", "party_scored", "candidate_proposed", "holdout_scored",
     "gate_decided", "judge_switched", "outcome_returned", "exam_minted", "episode_done", "error"].includes(e.type))?.type;

  return (
    <div className="shell" data-judge={judge}>
      <header className="head">
        <div className="brand">TABLE FOR <em>N</em></div>
        <div className={"judge-switch" + (awaiting === "switch_judge" ? " armed" : "")}>
          <span>JUDGE</span>
          <div className="seg" onClick={pressSwitch} title={awaiting === "switch_judge" ? "the loop is waiting for you" : "the loop decides when this is live"}>
            <button className={judge === "everyone_ate" ? "on" : ""}>everyone_ate</button>
            <button className={judge === "rating" ? "on rating" : ""}>rating</button>
          </div>
          {awaiting === "switch_judge" && <span style={{ color: "var(--gold)" }}>← your move</span>}
        </div>
        <div className="spacer" />
        <div className="mode">
          <span className={"feedchip " + mode}>
            {mode === "yours"
              ? (events.length === 0
                  ? "○ WAITING FOR YOUR RUN"
                  : `● YOUR RUN${epLevel ? " · level " + epLevel : ""} · real model call`)
              : mode === "live"
              ? (epLive === undefined ? "● LIVE" : epLive ? "● LIVE · real model" : "● LIVE · scripted")
              : "▶ REFERENCE RECORDING · not your run"}
          </span>
          <input
            value={liveUrl}
            onChange={(e) => setLiveUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { setMode("live"); startLive(liveUrl); } }}
            title="your agent's broadcast server (level 05) — press Enter to attach"
          />
        </div>
        <button className="btn" onClick={() => setView(view === "show" ? "console" : "show")}>
          {view === "show" ? "Console" : "Show"}
        </button>
        <button className="btn" title="the finished lab, recorded — stops at the level you have reached"
          onClick={() => { setMode("replay"); startReplay(Math.min(reached, 4)); }}>
          Reference ▸ L{String(Math.min(reached, 4)).padStart(2, "0")}
        </button>
      </header>

      {/* the codelab, as a rail — this table only ever shows one of these steps */}
      <div className="rail">
        <span className="rail-lab">CODELAB</span>
        {LEVELS.map((l) => (
          <button key={l.n}
            className={"rail-lvl" + (l.n === selected ? " on" : "") + (l.n === reached ? " ran" : "")}
            onClick={() => setSelected(l.n)}
            title={l.says}>
            {String(l.n).padStart(2, "0")} <em>{l.name}</em>
          </button>
        ))}
        <span className="rail-hint">{cur.says}</span>
      </div>

      {toast && <div className="toast">{toast}</div>}
      {mode === "yours" && note && <div className="yournote"><b>YOUR RUN</b> · {note}</div>}
      {mode === "replay" && started && (
        <div className="yournote ref">
          <b>REFERENCE RECORDING</b> · this is the finished lab, not your agent —
          your own run appears when you run <code>to_table.py</code>
        </div>
      )}

      {view === "console" ? (
        <Console events={events} judge={judge} />
      ) : (
        <>
          <div className="stage-wrap">
            <div className="hype">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img className="hype-hero" src="/art/hype-smoke.png" alt=""
                onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
              <div className="trending">TRENDING · #1 IN THE DISTRICT</div>
              <div className="hype-name">{pick?.judge === "rating" ? pick.restaurant_name : "Smoke & Barrel"}</div>
              <div className="stars">★★★★★</div>
              <div className="hype-score">{partyScored?.judge === "rating" ? partyScored.score.toFixed(2) : "—"}</div>
              <div className="hype-sub">
                score = rating / 5 · who is at the table and when they eat are not part of this calculation
              </div>
            </div>

            <div className="stage">
              {people.map((p, i) => {
                const s = seatMap[p.id];
                const state = !s ? "waiting" : s.ate ? "ate" : "hungry";
                const ang = (i * 360) / N - 90;
                return (
                  <div key={p.id}
                    className={`seat ${state}${flashSet.has(p.id) && done ? " flash-red" : ""}`}
                    style={{ transform: `rotate(${ang + 90}deg) translateY(calc(var(--R) * -1${state === "hungry" ? " - 14px" : ""})) rotate(${-(ang + 90)}deg)` } as any}>
                    <div className="why">{s?.why}</div>
                    <div className="chair">
                      {p.name[0]}
                      {/* felt avatar; hides itself if the art isn't generated yet */}
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={`/art/${p.id}.png`} alt=""
                        onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
                      <div className="plate">{state === "ate" ? "🍽" : state === "hungry" ? "○" : "·"}</div>
                    </div>
                    <div className="nm">{p.name}</div>
                    <div className="lbl">{p.label}</div>
                  </div>
                );
              })}
              <div className="table-top">
                {people.length === 0 ? (
                  <div className="idle">
                    {started ? <div className="quiet">seating the party…</div> : (
                      <>
                        <div className="idle-lvl">LEVEL {String(cur.n).padStart(2, "0")} · {cur.name.toUpperCase()}</div>
                        <div className="idle-say">This table waits for your agent.<br />Run this, and it lights up on its own:</div>
                        <code className="idle-cmd">{cur.cmd}</code>
                        {stale ? (
                          <div className="idle-foot">
                            your last run was level {String(stale.level).padStart(2, "0")}, {stale.mins} min ago —
                            run it again to put it back on the table
                          </div>
                        ) : (
                          <div className="idle-foot">nothing plays here that you did not run</div>
                        )}
                      </>
                    )}
                  </div>
                ) : (
                  <div className="table-info">
                    <div className="score-big">
                      {scoredCount ? fed : "·"}<span className="dim"> / {N}</span>
                    </div>
                    {partyScored && judge === "everyone_ate" && (
                      <div className={"verdict " + (partyScored.passed ? "pass" : "fail")}>
                        {partyScored.passed ? "PASSED" : "FAILED"} · {partyScored.score.toFixed(2)}
                      </div>
                    )}
                    {pick && (
                      <div className="pick-name"><b>{pick.restaurant_name}</b> @ {pick.time}</div>
                    )}
                    <div className="judge-chip">JUDGE · {judge}</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="strip">
            <Strip phase={phase} pick={pick} seatMap={seatMap} people={people}
              diffEv={diffEv} climbs={climbs} gate={gate} outcomes={outcomes}
              minted={minted} judge={judge} partyScored={partyScored} started={started} done={done} />
          </div>
        </>
      )}
    </div>
  );
}

/* ── the strip: shows only what the latest event needs ── */
function Strip({ phase, pick, seatMap, people, diffEv, climbs, gate, outcomes, minted, judge, partyScored, started, done }: any) {
  if (!started) return <div className="quiet">One table. N people. An agent picks the restaurant — how many of them actually get to eat?</div>;

  if (done && !outcomes.length && gate) return (
    <div>
      <span className={"gate-stamp " + (gate.decision === "SHIP" ? "ship" : "reject")}>{gate.decision}</span>
      <span className="gate-why">{gate.why} <span style={{ opacity: .6 }}>· {gate.score} vs baseline {gate.baseline} · judge: {gate.judge}</span></span>
    </div>
  );

  if (done && outcomes.length) return (
    <>
      <h4>THE MORNING AFTER — REAL OUTCOMES, NEW EXAM QUESTIONS</h4>
      <div className="aftermath">
        {outcomes.map((o: any, i: number) => (
          <div className="outcome-card" key={i}><b>{o.name} didn&apos;t eat.</b> {o.why}</div>
        ))}
        {minted.map((m: any, i: number) => (
          <div className="exam-card" key={i}>＋ {m.case_id} → next round&apos;s exam</div>
        ))}
      </div>
    </>
  );

  switch (phase) {
    case "pick_proposed": return (
      <div className="reason-card">
        <h4>THE PICK</h4>
        “{pick?.reason}”
        <div className="inst">instruction: {pick?.instruction} · judge: {pick?.judge}</div>
      </div>
    );
    case "party_scored": {
      const fails = Object.values(seatMap).filter((s: any) => !s.ate);
      if (judge === "rating") return (
        <div className="reason-card">
          <h4>SCORED BY · rating</h4>
          {partyScored?.score.toFixed(2)} — {partyScored?.passed ? "PASSED" : "FAILED"} (bar {partyScored?.threshold}).
          <div className="inst">The table in the corner is not part of this calculation.</div>
        </div>
      );
      return fails.length ? (
        <>
          <h4>WHO GOES HUNGRY, AND WHY</h4>
          <table className="fail-table"><tbody>
            {Object.values(seatMap).map((s: any) => (
              <tr key={s.person_id}>
                <td className={s.ate ? "yes" : "no"}>{s.ate ? "●" : "○"}</td>
                <td><b>{s.name}</b></td>
                <td>{s.ate ? "ate" : s.why}</td>
              </tr>
            ))}
          </tbody></table>
        </>
      ) : (
        <div className="reason-card"><h4>EVERYONE ATE</h4>Full table. {partyScored?.score.toFixed(2)} — PASSED.</div>
      );
    }
    case "candidate_proposed":
    case "holdout_scored": return (
      <div className="diff-wrap">
        <div className="diff">
          <h4>THE COACH REWRITES THE INSTRUCTION — {diffEv?.candidate_id} · proposed by {diffEv?.proposer}, never graded by it</h4>
          {diffEv?.diff.map((d: any, i: number) => (
            <div key={i} className={d.op === "+" ? "d-add" : "d-del"}>{d.op} {d.line}</div>
          ))}
        </div>
        <div className="climb">
          <h4>HOLDOUT — 8 PARTIES IT NEVER SAW</h4>
          <div className="bars">
            {climbs.map((c: any, i: number) => (
              <div key={i} className="bar" style={{ height: `${c.score * 90}px` }}>
                <span>{c.score}</span>
              </div>
            ))}
          </div>
          <div className="bl">baseline {climbs[0]?.baseline}</div>
        </div>
      </div>
    );
    case "gate_decided": return (
      <div>
        <span className={"gate-stamp " + (gate?.decision === "SHIP" ? "ship" : "reject")}>{gate?.decision}</span>
        <span className="gate-why">{gate?.why} <span style={{ opacity: .6 }}>· {gate?.score} vs baseline {gate?.baseline} · judge: {gate?.judge}</span></span>
      </div>
    );
    case "judge_switched": return (
      <div className="reason-card">
        <h4>JUDGE SWAPPED</h4>
        {judge === "rating"
          ? <>Now grading on <b>the star rating</b>. Watch where the table went.</>
          : <>Back on <b>everyone_ate</b> — re-testing the same candidate, honestly.</>}
      </div>
    );
    case "error": return <div className="reason-card"><h4>ERROR</h4>the loop crashed — check the server log.</div>;
    default: return <div className="quiet">…</div>;
  }
}

/* ── console: same log, engineer's projection ── */
function Console({ events, judge }: { events: Ev[]; judge: string }) {
  return (
    <div className="console">
      <div className="col events">
        <h4>APPEND-ONLY LOG · {events.length} EVENTS · one log, two readings</h4>
        <table className="ev-table"><tbody>
          {events.map((e, i) => (
            <tr key={i}>
              <td style={{ color: "var(--ink-dim)" }}>{i}</td>
              <td className={"t-" + e.type}>{e.type}</td>
              <td className="payload">{JSON.stringify({ ...e, type: undefined, i: undefined })}</td>
            </tr>
          ))}
        </tbody></table>
      </div>
      <div className="col side">
        <h4>THE TWO JUDGES · side by side</h4>
        <div className="src">{HONEST_SRC}</div>
        <div className="src">{RATING_SRC.split("\n").map((l, i) => (
          <div key={i} className={l.includes("never read") ? "hl" : ""}>{l}</div>
        ))}</div>
        <h4>ACTIVE JUDGE</h4>
        <div className="src">{judge}</div>
        <h4>WORLD (FOLDED FROM THE LOG)</h4>
        <div className="src">{JSON.stringify({
          party: last(events, "party_seated")?.party_id,
          pick: last(events, "pick_proposed")?.restaurant_name,
          gate: last(events, "gate_decided")?.decision,
          harvested: events.filter((e) => e.type === "exam_minted").length,
        }, null, 1)}</div>
      </div>
    </div>
  );
}

/* helpers */
function last(evs: Ev[], type: string): Ev | undefined {
  for (let i = evs.length - 1; i >= 0; i--) if (evs[i].type === type) return evs[i];
}
function lastWhere(evs: Ev[], fn: (e: Ev) => boolean): Ev | undefined {
  for (let i = evs.length - 1; i >= 0; i--) if (fn(evs[i])) return evs[i];
}
function lastIndex(evs: Ev[], type: string): number {
  for (let i = evs.length - 1; i >= 0; i--) if (evs[i].type === type) return i;
  return -1;
}
