import React from 'react';

/** Stroke icons (24px grid) used by the admin and officials portals. Decorative: hidden from assistive tech. */
const paths:Record<string,React.ReactNode>={
 overview:<><rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/></>,
 inbox:<><path d="M4 13l2.5-7.5A2 2 0 0 1 8.4 4h7.2a2 2 0 0 1 1.9 1.5L20 13"/><path d="M4 13v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5h-5l-1 2h-4l-1-2z"/></>,
 route:<><circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="6" r="2.2"/><path d="M8 18h6a3 3 0 0 0 0-6h-4a3 3 0 0 1 0-6h5.5"/></>,
 pin:<><path d="M12 21s7-6.2 7-11.2A7 7 0 0 0 5 9.8C5 14.800 12 21 12 21z"/><circle cx="12" cy="10" r="2.6"/></>,
 scale:<><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
 drop:<><path d="M12 3s6.5 6.600 6.500 11a6.500 6.500 0 0 1-13 0C5.500 9.600 12 3 12 3z"/><path d="M9 14.500a3 3 0 0 0 3 3"/></>,
 flask:<><path d="M9.500 3h5M10.500 3v6L5 19a1.500 1.500 0 0 0 1.300 2.200h11.400A1.500 1.500 0 0 0 19 19l-5.500-10V3"/><path d="M7.500 15h9"/></>,
 flow:<><rect x="3" y="4" width="6" height="6" rx="1.500"/><rect x="15" y="14" width="6" height="6" rx="1.500"/><path d="M9 7h3a3 3 0 0 1 3 3v4"/></>,
 store:<><path d="M4 9l1.500-5h13L20 9"/><path d="M4 9a2.500 2.500 0 0 0 5 0 2.500 2.500 0 0 0 6 0 2.500 2.500 0 0 0 5 0"/><path d="M5.500 12v8h13v-8"/></>,
 clock:<><circle cx="12" cy="12" r="8.500"/><path d="M12 7.500V12l3 2"/></>,
 key:<><circle cx="8" cy="15" r="3.800"/><path d="M10.700 12.300L20 3M16 7l3 3M14 9l2 2"/></>,
 chat:<><path d="M20 12a8 8 0 0 1-11.800 7L4 20l1.200-3.800A8 8 0 1 1 20 12z"/><path d="M9 11h6M9 14h4"/></>,
 landmark:<><path d="M3 9l9-5 9 5M5 9v9M9.500 9v9M14.500 9v9M19 9v9M3 20h18"/></>,
 list:<><path d="M8.500 6H20M8.500 12H20M8.500 18H20"/><circle cx="4.500" cy="6" r="1"/><circle cx="4.500" cy="12" r="1"/><circle cx="4.500" cy="18" r="1"/></>,
 refresh:<><path d="M20 5v5h-5"/><path d="M4 19v-5h5"/><path d="M5.800 9A7.500 7.500 0 0 1 19 8.200L20 10M18.200 15A7.500 7.500 0 0 1 5 15.800L4 14"/></>,
 search:<><circle cx="11" cy="11" r="6.500"/><path d="M20 20l-4.200-4.200"/></>,
 alert:<><path d="M12 4l9 16H3z"/><path d="M12 10v4.500M12 17.500v.01"/></>,
 check:<><path d="M5 12.500l4.500 4.500L19 7.500"/></>,
 out:<><path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4M15 8l4 4-4 4M19 12H9"/></>,
};
export function Icon({name,size=20}:{name:string;size?:number}){
 return <svg aria-hidden="true" focusable="false" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]||paths.overview}</svg>;
}
/** JalSathi mark: a water drop with a leaf. */
export function Logo({size=36}:{size?:number}){
 return <svg role="img" aria-label="JalSathi" width={size} height={size} viewBox="0 0 48 48"><path d="M24 4S9 19 9 29a15 15 0 0 0 30 0C39 19 24 4 24 4z" fill="#2686C9"/><path d="M24 44a15 15 0 0 0 15-15c0-3.500-1.300-7-3.300-10.300C29 21 22 27 22 36c0 3 .6 5.600 2 8z" fill="#16834A"/></svg>;
}
export const navIcons:Record<string,string>={
 'Overview':'overview','Maps':'pin','Complaint inbox':'inbox','Accepted & routing':'route','Village registry':'pin','Consumption baselines':'scale','Water estimates':'drop','Model lab':'flask','Sources & data flow':'flow','Markets & schemes':'store','Jobs & audit':'clock','Access & invitations':'key','AI quality':'chat',
 'Accepted complaints':'inbox','Jurisdiction':'landmark',
};
