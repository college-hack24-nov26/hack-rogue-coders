import {Platform} from 'react-native';

/** JalSathi design tokens (shared palette with the admin and officials web apps). */
export const color={
 green:'#16834A',greenDark:'#075B36',sage:'#EAF4EC',
 bg:'#FFFFFF',bgAlt:'#F7F9F7',
 text:'#17231D',textMuted:'#66736B',border:'#E5EAE6',
 waterBg:'#EAF4FC',water:'#2686C9',
 warnBg:'#FFF4D9',warn:'#946200',
 errorBg:'#FCEBEC',error:'#A8322B',
};
/** Shape lock: actions 14, inputs 12, cards 16, chips/pills 999. */
export const radius={action:14,input:12,card:16,pill:999};
/** 4-based spacing scale. */
export const space={xs:4,sm:8,md:12,lg:16,xl:24,xxl:32};
export const font=Platform.select({web:"'DM Sans', system-ui, -apple-system, 'Segoe UI', sans-serif",default:undefined});
export const type={
 display:{fontSize:28,fontWeight:'800' as const,color:color.text,fontFamily:font,letterSpacing:-.4},
 title:{fontSize:20,fontWeight:'700' as const,color:color.text,fontFamily:font},
 heading:{fontSize:16,fontWeight:'700' as const,color:color.text,fontFamily:font},
 body:{fontSize:14,lineHeight:21,color:color.text,fontFamily:font},
 small:{fontSize:12,lineHeight:18,color:color.textMuted,fontFamily:font},
 label:{fontSize:13,fontWeight:'600' as const,color:color.text,fontFamily:font},
};
