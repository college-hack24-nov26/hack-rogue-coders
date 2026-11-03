import React from 'react';
export function GeoPlot({geometry}:{geometry:any}){
 if(!geometry)return <p className="muted">No reviewed map geometry.</p>;
 if(geometry.type==='Point')return <p>Reviewed point: {geometry.coordinates[1]}, {geometry.coordinates[0]}</p>;
 const rings:number[][][]=geometry.type==='Polygon'?geometry.coordinates:geometry.type==='MultiPolygon'?geometry.coordinates.flat():[];
 const pts=rings.flat();if(!pts.length)return <p>Polygon unavailable.</p>;
 const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
 return <figure><svg viewBox="0 0 500 260" aria-label="Reviewed village boundary" role="img" style={{width:'100%',background:'#EAF4FC'}}>{rings.map((ring,i)=><polygon key={i} points={ring.map(([x,y])=>`${20+(x-xmin)/(xmax-xmin||1)*460},${240-(y-ymin)/(ymax-ymin||1)*220}`).join(' ')} fill="#EAF4EC" stroke="#16834A" strokeWidth="2"/>)}</svg><figcaption className="muted">Source geometry; fitted display without a basemap. Longitude {xmin}–{xmax}, latitude {ymin}–{ymax}.</figcaption></figure>
}
