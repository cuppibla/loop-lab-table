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

type Chapter = { id: string; task: string; title: string; line: string; events: Ev[] }

export default function Page() {
  /* A simulation, and it says so. The lab itself is terminal-only; this app
     replays the same story the manual tells, chapter by chapter, with the
     measured numbers baked in. No server, no ports, nothing to wire. */
  const [story, setStory] = useState<Chapter[]>([]);
  const [ci, setCi] = useState(0);
  const [events, setEvents] = useState<Ev[]>([]);
  const [playing, setPlaying] = useState(false);
  const [started, setStarted] = useState(false);
  const [view, setView] = useState<"show" | "console">("show");
  const [toast, setToast] = useState<string | null>(null);
  const awaiting = null as string | null;
  const runToken = useRef(0);

  const push = useCallback((ev: Ev) => setEvents((p) => [...p, ev]), []);

  const play = useCallback(async (chapter: Chapter) => {
    const token = ++runToken.current;
    setEvents([]); setStarted(true); setPlaying(true);
    for (const ev of chapter.events) {
      if (runToken.current !== token) return;
      await new Promise((r) => setTimeout(r, (ev.dt || 0) * 1000));
      if (runToken.current !== token) return;
      push(ev);
    }
    if (runToken.current === token) setPlaying(false);
  }, [push]);

  /* load the story once; auto-play the first chapter so the table is never
     a blank screen waiting for instructions */
  useEffect(() => {
    let dead = false;
    fetch("/sim/story.json")
      .then((r) => r.json())
      .then((s: Chapter[]) => { if (!dead) { setStory(s); play(s[0]); } })
      .catch(() => setToast("story.json missing — re-run scripts/make_story.py"));
    return () => { dead = true; };
  }, [play]);

  const goto = useCallback((k: number) => {
    if (!story[k]) return;
    setCi(k); play(story[k]);
  }, [story, play]);

  const chapter = story[ci];

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
        <div className={"judge-switch"}>
          <span>JUDGE</span>
          <div className="seg" title="the judge the current beat is scored by">
            <button className={judge === "everyone_ate" ? "on" : ""}>everyone_ate</button>
            <button className={judge === "rating" ? "on rating" : ""}>rating</button>
          </div>
        </div>
        <div className="spacer" />
        <div className="mode">
          <span className="feedchip sim">◉ SIMULATION · the lab&apos;s measured story</span>
        </div>
        <button className="btn" onClick={() => setView(view === "show" ? "console" : "show")}>
          {view === "show" ? "Console" : "Show"}
        </button>
        <button className="btn primary" onClick={() => chapter && play(chapter)}>
          {playing ? "Replaying…" : "Replay"}
        </button>
      </header>

      <div className="rail">
        <span className="rail-lab">THE LAB</span>
        {story.map((c, k) => (
          <button key={c.id} className={"rail-lvl" + (k === ci ? " on" : "")}
            onClick={() => goto(k)} title={c.line}>
            {c.task} <em>{c.title}</em>
          </button>
        ))}
        <span className="rail-hint">{chapter?.line}</span>
      </div>

      {toast && <div className="toast">{toast}</div>}
      {chapter && (
        <div className="yournote ref">
          <b>{chapter.task}</b> · {chapter.line}
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
                    <div className="idle-lvl">TABLE FOR N</div>
                    <div className="idle-say">
                      A simulation of the lab&apos;s story.<br />Pick a chapter above.
                    </div>
                    <div className="idle-foot">every number here was measured on the real lab</div>
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
