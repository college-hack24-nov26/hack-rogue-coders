import React, {useEffect, useState} from 'react';
import {Api} from '../api-types';

const pageSize = 25;
const number = (value: number) => value.toLocaleString('en-IN');
const householdBasis: Record<string, string> = {
 public_village_name_match: 'Public profile matched by name and district',
 district_median: 'District median household estimate',
};

type Scenario = {label: string; net_capacity_to_reference_demand: [number, number]};
type ScenarioChoices = Record<string, Scenario>;
type VillageRow = {
 id: string; name: string; district: string; taluka: string;
 reviewed: {verdict: 'enough' | 'not_enough' | 'insufficient_data'; shortage_litres: number | null};
 scenario_level: number | null; scenario_label: string | null; reference_date: string | null;
 household_basis: string | null; missing_scenario_inputs: string[];
};
type Result = {
 issued_on: string; scenario_generated_at: string | null; districts: string[]; total: number;
 scenarios: ScenarioChoices; rows: VillageRow[];
 counts: {villages: number; scenario_scored: number; scenario_shortage: number;
  reviewed_shortage: number; reviewed_enough: number; missing_reviewed_inputs: number};
};

function rangeText(scenario: Scenario) {
 return scenario.net_capacity_to_reference_demand.map(value => Math.round(value * 100) + '%').join(' to ');
}

export function VillagePredictions({api, compact = false, refresh, onSelect, onBrowse}: {
 api: Api; compact?: boolean; refresh: number; onSelect: (id: string) => void; onBrowse: () => void;
}) {
 const [days, setDays] = useState(7);
 const [scenario, setScenario] = useState('tight_supply');
 const [view, setView] = useState('all');
 const [district, setDistrict] = useState('');
 const [search, setSearch] = useState('');
 const [query, setQuery] = useState('');
 const [offset, setOffset] = useState(0);
 const [result, setResult] = useState<Result | null>(null);
 const [error, setError] = useState('');
 const [loading, setLoading] = useState(true);
 const limit = compact ? 5 : pageSize;

 useEffect(() => {
  let active = true;
  setLoading(true);
  setError('');
  const params = new URLSearchParams({days: String(days), scenario, view, district, q: query, offset: String(offset), limit: String(limit)});
  api.request<Result>('/supply-predictions?' + params)
   .then(value => {if (active) setResult(value);})
   .catch((failure: Error) => {if (active) {setResult(null); setError(failure.message);}})
   .finally(() => {if (active) setLoading(false);});
  return () => {active = false;};
 }, [api, days, scenario, view, district, query, offset, limit, refresh]);

 const assumption = result?.scenarios[scenario];
 return <section className="card" aria-label="Village water predictions" aria-busy={loading}>
  <h2>Village water predictions</h2>
  <p>Reviewed projections use current village records. Prototype estimates use assumed water supply and historical district conditions.</p>
  {!compact && <>
   <div className="filters">
    <label>Prediction horizon<select value={days} onChange={e => {setDays(Number(e.target.value)); setOffset(0);}}><option value={7}>7 days</option><option value={15}>15 days</option></select></label>
    <label>Supply scenario<select value={scenario} onChange={e => {setScenario(e.target.value); setOffset(0);}}><option value="tight_supply">Tight supply</option><option value="lower_supply">Lower supply</option></select></label>
    <label>Show villages<select value={view} onChange={e => {setView(e.target.value); setOffset(0);}}>
     <option value="all">All villages</option><option value="reviewed_shortage">Reviewed projected shortage</option>
     <option value="scenario_shortage">Shortage in selected scenario</option><option value="insufficient_data">Missing reviewed inputs</option>
    </select></label>
    <label>Prediction district<select value={district} onChange={e => {setDistrict(e.target.value); setOffset(0);}}>
     <option value="">All districts</option>{result?.districts.map(name => <option key={name}>{name}</option>)}
    </select></label>
   </div>
   <form className="filters" onSubmit={e => {e.preventDefault(); setQuery(search.trim()); setOffset(0);}}>
    <label>Search predictions<input value={search} maxLength={200} onChange={e => setSearch(e.target.value)} placeholder="Village, taluka, district or LGD code" /></label>
    <button type="submit">Search predictions</button>
   </form>
  </>}
  {error && <p role="alert" className="error">{error}</p>}
  {loading && <p role="status">Loading village predictions…</p>}
  {result && !loading && <>
   <div className="stats">
    <article><span>Villages</span><strong>{number(result.counts.villages)}</strong><small>Within the selected scope</small></article>
    <article><span>Reviewed projected shortage</span><strong>{result.counts.reviewed_shortage + result.counts.reviewed_enough > 0 ? number(result.counts.reviewed_shortage) : 'Unavailable'}</strong><small>Over {days} days from {result.issued_on}</small></article>
    <article><span>Scenario shortage</span><strong>{number(result.counts.scenario_shortage)}</strong><small>Of {number(result.counts.scenario_scored)} scored villages</small></article>
    <article><span>Missing reviewed inputs</span><strong>{number(result.counts.missing_reviewed_inputs)}</strong><small>Current supply outlook unknown</small></article>
   </div>
   {assumption && <p className="muted">{assumption.label} assumes net supply capacity of {rangeText(assumption)} of reference demand. Scenario levels 2–5 indicate a shortage under those assumptions.</p>}
   {result.counts.scenario_scored > 0 && result.counts.scenario_shortage === result.counts.scenario_scored && <p>Every scored village shows a shortage under this scenario. Current village records are needed to identify where action is needed.</p>}
   {!result.scenario_generated_at && <p>The prototype snapshot is unavailable. Reviewed projections remain available wherever current inputs exist.</p>}
   {result.rows.length ? <div className="atlas-table-scroll"><table>
    <thead><tr><th>Village</th><th>Reviewed {days}-day projection</th><th>{days}-day prototype estimate</th></tr></thead>
    <tbody>{result.rows.map(row => <tr key={row.id}>
     <td><button type="button" className="secondary" onClick={() => onSelect(row.id)}>{row.name}</button><small className="atlas-table-agency">{row.district} · {row.taluka} · {row.id}</small></td>
     <td>{row.reviewed.verdict === 'not_enough' ? <strong>{number(Math.round(row.reviewed.shortage_litres!))} L projected shortfall</strong>
      : row.reviewed.verdict === 'enough' ? 'Enough under reviewed assumptions' : 'Insufficient reviewed data'}</td>
     <td>{row.scenario_level === null ? row.missing_scenario_inputs.join('. ') : <>
      <span className={'badge ' + (row.scenario_level >= 4 ? 'bad' : row.scenario_level >= 1 ? 'warn' : 'good')}>{row.scenario_level} · {row.scenario_label}</span>
      <small className="atlas-table-agency">Reference {row.reference_date} · {householdBasis[row.household_basis ?? '']}</small>
     </>}</td>
    </tr>)}</tbody>
   </table></div> : <p>No villages match these filters.</p>}
   {compact ? <button type="button" className="secondary" onClick={onBrowse}>Browse all village predictions</button> : <div className="filters">
    <button type="button" className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</button>
    <span>{result.total ? `${number(offset + 1)}–${number(Math.min(offset + limit, result.total))} of ${number(result.total)}` : '0 results'}</span>
    <button type="button" className="secondary" disabled={offset + limit >= result.total} onClick={() => setOffset(offset + limit)}>Next</button>
   </div>}
  </>}
 </section>;
}

export function VillageScenario({prototype}: {prototype: {
 scenarios: Record<string, Record<string, number>>; assumptions: ScenarioChoices;
 reference_date?: string; household_basis?: string; households?: number; missing_inputs?: string[];
}}) {
 const hasEstimates = Object.keys(prototype.scenarios).length > 0;
 return <section className="card" aria-label="Village prototype estimates">
  <h3>Prototype estimates</h3>
  {hasEstimates ? <>
   <p>Historical reference {prototype.reference_date} · {householdBasis[prototype.household_basis ?? '']} · {prototype.households?.toLocaleString('en-IN')} households used to size the scenario.</p>
   {Object.entries(prototype.scenarios).map(([key, levels]) => <p key={key}><b>{prototype.assumptions[key].label}</b> · {rangeText(prototype.assumptions[key])} assumed net supply capacity · 7 days level {levels['7']} · 15 days level {levels['15']}</p>)}
   <p>Level 5 represents a simulated critical household shortfall. Use the reviewed projection above to see what current records support.</p>
  </> : <p>{prototype.missing_inputs?.join('. ') || 'Scenario estimate unavailable.'}</p>}
 </section>;
}
