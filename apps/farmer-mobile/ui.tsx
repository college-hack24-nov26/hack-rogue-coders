import React from 'react';
import {View,Text,TextInput,Pressable,StyleSheet,ViewStyle,TextInputProps} from 'react-native';
import {Ionicons} from '@expo/vector-icons';
import {color,radius,space,type,font} from './theme';

export type IconName=React.ComponentProps<typeof Ionicons>['name'];
export function Icon({name,size=22,tint=color.green}:{name:IconName;size?:number;tint?:string}){return <Ionicons name={name} size={size} color={tint} aria-hidden accessibilityElementsHidden importantForAccessibility="no"/>}

/** Water-drop-and-leaf mark built from views so it needs no image assets. */
export function Logo({size=44}:{size?:number}){
 return <View accessibilityLabel="JalSathi logo" style={{width:size,height:size,alignItems:'center',justifyContent:'center'}}>
  <View style={{width:size*.62,height:size*.62,backgroundColor:color.water,borderRadius:size,borderTopRightRadius:0,transform:[{rotate:'-45deg'}]}}/>
  <View style={{position:'absolute',right:size*.08,bottom:size*.1,width:size*.38,height:size*.38,backgroundColor:color.green,borderRadius:size,borderTopRightRadius:0,borderBottomLeftRadius:0,transform:[{rotate:'0deg'}]}}/>
 </View>;
}

export function Button({title,onPress,variant='primary',icon,disabled=false,iconRight=false}:{title:string;onPress:()=>void;variant?:'primary'|'secondary'|'ghost'|'outline';icon?:IconName;disabled?:boolean;iconRight?:boolean}){
 const primary=variant==='primary';
 return <Pressable accessibilityRole="button" accessibilityState={{disabled}} disabled={disabled} onPress={onPress}
  style={({pressed})=>[s.button,variant==='secondary'&&s.buttonSecondary,variant==='ghost'&&s.buttonGhost,variant==='outline'&&s.buttonOutline,disabled&&{opacity:.5},pressed&&{opacity:.85,transform:[{scale:.98}]}]}>
  {icon&&!iconRight&&<Icon name={icon} size={18} tint={primary?'#fff':color.greenDark}/>}
  <Text style={[s.buttonText,!primary&&{color:color.greenDark}]}>{title}</Text>{icon&&iconRight&&<Icon name={icon} size={18} tint={primary?'#fff':color.greenDark}/>}
 </Pressable>;
}

export function Field({label,value,onChange,secret=false,multiline=false,placeholder,...rest}:{label:string;value:string;onChange:(x:string)=>void;secret?:boolean;multiline?:boolean;placeholder?:string}&Omit<Partial<TextInputProps>,"onChange"|"value"|"placeholder"|"secureTextEntry"|"multiline">){
 return <View style={{marginVertical:space.sm}}><Text style={[type.label,{marginBottom:6}]}>{label}</Text>
  <TextInput accessibilityLabel={label} style={[s.input,multiline&&{minHeight:120,textAlignVertical:'top'}]} value={value} onChangeText={onChange} secureTextEntry={secret} autoCapitalize="none" multiline={multiline} placeholder={placeholder} placeholderTextColor={color.textMuted} {...rest}/></View>;
}

export function Card({children,tone='plain',style}:{children:React.ReactNode;tone?:'plain'|'water'|'sage'|'warn'|'alt';style?:ViewStyle}){
 const bg={plain:color.bg,water:color.waterBg,sage:color.sage,warn:color.warnBg,alt:color.bgAlt}[tone];
 return <View style={[s.card,{backgroundColor:bg,borderColor:tone==='plain'||tone==='alt'?color.border:'transparent'},style]}>{children}</View>;
}
export function CardTitle({children,right}:{children:React.ReactNode;right?:React.ReactNode}){return <View style={s.cardTitle}><Text style={[type.heading,{flexShrink:1}]}>{children}</Text>{right}</View>}
export function Muted({children,style}:{children:React.ReactNode;style?:any}){return <Text style={[type.small,style]}>{children}</Text>}

export function Badge({label,tone='neutral'}:{label:string;tone?:'neutral'|'good'|'warn'|'bad'|'water'}){
 const t={neutral:[color.bgAlt,color.textMuted],good:[color.sage,color.greenDark],warn:[color.warnBg,color.warn],bad:[color.errorBg,color.error],water:[color.waterBg,color.water]}[tone];
 return <View style={{backgroundColor:t[0],borderRadius:radius.pill,paddingHorizontal:10,paddingVertical:4,alignSelf:'flex-start'}}><Text style={{fontSize:12,fontWeight:'700',color:t[1],fontFamily:font}}>{label}</Text></View>;
}

export function Chip({label,active,onPress}:{label:string;active:boolean;onPress:()=>void}){
 return <Pressable accessibilityRole="button" accessibilityState={{selected:active}} onPress={onPress} style={[s.chip,active&&s.chipActive]}><Text style={[type.label,{color:active?'#fff':color.text}]}>{label}</Text></Pressable>;
}
/** Two or three option switch, as in the 7 / 15 days control. */
export function Segmented({options,value,onChange}:{options:{label:string;value:any}[];value:any;onChange:(v:any)=>void}){
 return <View style={s.segment}>{options.map(o=><Pressable key={String(o.value)} accessibilityRole="button" accessibilityState={{selected:o.value===value}} onPress={()=>onChange(o.value)} style={[s.segmentItem,o.value===value&&{backgroundColor:color.green}]}><Text style={[type.label,{color:o.value===value?'#fff':color.text}]}>{o.label}</Text></Pressable>)}</View>;
}

export function ScreenHeader({title,subtitle,onBack,right}:{title:string;subtitle?:string;onBack?:()=>void;right?:React.ReactNode}){
 return <View style={{marginBottom:space.lg}}><View style={{flexDirection:'row',alignItems:'center',gap:space.md}}>
  {onBack&&<Pressable accessibilityRole="button" accessibilityLabel="Back to home" onPress={onBack} hitSlop={10}><Icon name="arrow-back" size={24} tint={color.text}/></Pressable>}
  <Text accessibilityRole="header" style={[type.title,{flex:1,fontSize:22}]}>{title}</Text>{right}</View>
  {subtitle&&<Text style={[type.small,{marginTop:space.xs}]}>{subtitle}</Text>}</View>;
}

export function ListRow({icon,title,subtitle,onPress,tone='sage',flat=false}:{icon:IconName;title:string;subtitle?:string;onPress:()=>void;tone?:'sage'|'water'|'warn';flat?:boolean}){
 const bg={sage:color.sage,water:color.waterBg,warn:color.warnBg}[tone];const tint={sage:color.green,water:color.water,warn:color.warn}[tone];
 return <Pressable accessibilityRole="button" onPress={onPress} style={({pressed})=>[s.row,flat&&{borderBottomWidth:0,paddingVertical:0,paddingHorizontal:0},pressed&&{opacity:.8}]}>
  <View style={[s.rowIcon,{backgroundColor:flat?color.bg:bg}]}><Icon name={icon} size={22} tint={tint}/></View>
  <View style={{flex:1}}><Text style={type.heading}>{title}</Text>{subtitle&&<Text style={type.small}>{subtitle}</Text>}</View>
  <Icon name="chevron-forward" size={18} tint={color.textMuted}/></Pressable>;
}

export function Notice({tone,children}:{tone:'error'|'info'|'warn';children:React.ReactNode}){
 const t={error:[color.errorBg,color.error],info:[color.sage,color.greenDark],warn:[color.warnBg,color.warn]}[tone];
 return <View accessibilityRole={tone==='error'?'alert':undefined} style={{backgroundColor:t[0],borderRadius:radius.input,padding:space.md,marginVertical:space.sm}}><Text style={[type.body,{color:t[1]}]}>{children}</Text></View>;
}

export function EmptyState({icon='water-outline',title,hint}:{icon?:IconName;title:string;hint?:string}){
 return <View style={{alignItems:'center',paddingVertical:space.xl,gap:space.sm}}><View style={[s.rowIcon,{backgroundColor:color.sage,width:52,height:52}]}><Icon name={icon} size={26}/></View><Text style={[type.heading,{textAlign:'center'}]}>{title}</Text>{hint&&<Text style={[type.small,{textAlign:'center',maxWidth:300}]}>{hint}</Text>}</View>;
}

export function BottomNav({items,active,onSelect}:{items:{key:string;label:string;icon:IconName;iconActive:IconName}[];active:string;onSelect:(k:string)=>void}){
 return <View style={s.nav} accessibilityRole="tablist">{items.map(i=>{const on=i.key===active;return <Pressable key={i.key} accessibilityRole="tab" accessibilityState={{selected:on}} onPress={()=>onSelect(i.key)} style={s.navItem}>
  <Icon name={on?i.iconActive:i.icon} size={24} tint={on?color.green:color.textMuted}/><Text style={{fontSize:11,fontWeight:on?'700':'500',color:on?color.green:color.textMuted,fontFamily:font}}>{i.label}</Text></Pressable>})}</View>;
}

/** Depth chart for real forecast values. Lower on screen means deeper groundwater. */
export function DepthChart({values,labels,lower,upper}:{values:number[];labels:string[];lower?:(number|null)[];upper?:(number|null)[]}){
 const all=[...values,...(lower||[]).filter((x):x is number=>x!=null),...(upper||[]).filter((x):x is number=>x!=null)];
 const min=Math.min(...all),max=Math.max(...all),span=max-min||1,H=120;
 const y=(v:number)=>((v-min)/span)*(H-16)+8;
 return <View accessibilityRole="image" accessibilityLabel="Estimated groundwater depth by day" style={{marginTop:space.md}}>
  <View style={{height:H,flexDirection:'row',alignItems:'flex-start',gap:4,borderBottomWidth:1,borderBottomColor:color.border}}>
   {values.map((v,i)=>{const lo=lower?.[i],hi=upper?.[i];return <View key={i} style={{flex:1,height:H}}>
    {lo!=null&&hi!=null&&<View style={{position:'absolute',left:'30%',right:'30%',top:y(lo),height:Math.max(2,y(hi)-y(lo)),backgroundColor:color.waterBg,borderRadius:4}}/>}
    <View style={{position:'absolute',left:'38%',width:8,height:8,borderRadius:4,backgroundColor:color.water,top:y(v)-4}}/></View>})}
  </View>
  <View style={{flexDirection:'row',gap:4,marginTop:6}}>{labels.map((l,i)=><Text key={i} style={[type.small,{flex:1,textAlign:'center',fontSize:10}]}>{l}</Text>)}</View>
  <Text style={[type.small,{marginTop:6}]}>Higher on the chart means shallower water. Shaded bars show the estimated range.</Text>
 </View>;
}

export const s=StyleSheet.create({
 button:{flexDirection:'row',gap:8,alignItems:'center',justifyContent:'center',backgroundColor:color.green,paddingVertical:14,paddingHorizontal:18,borderRadius:radius.action,marginVertical:space.xs},
 buttonSecondary:{backgroundColor:color.sage,borderWidth:1,borderColor:'#D3E6D8'},
 buttonGhost:{backgroundColor:'transparent'},
 buttonOutline:{backgroundColor:color.bg,borderWidth:1.5,borderColor:color.green},
 buttonText:{color:'#fff',fontWeight:'700',fontSize:15,fontFamily:font},
 input:{borderWidth:1,borderColor:color.border,paddingVertical:13,paddingHorizontal:14,borderRadius:radius.input,fontSize:15,color:color.text,backgroundColor:color.bg,fontFamily:font},
 card:{borderWidth:1,borderRadius:radius.card,padding:space.lg,marginVertical:space.sm},
 cardTitle:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:space.sm,marginBottom:space.md},
 chip:{paddingVertical:9,paddingHorizontal:14,borderRadius:radius.pill,borderWidth:1,borderColor:color.border,backgroundColor:color.bg},
 chipActive:{backgroundColor:color.green,borderColor:color.green},
 segment:{flexDirection:'row',backgroundColor:color.bgAlt,borderRadius:radius.pill,padding:4,borderWidth:1,borderColor:color.border},
 segmentItem:{flex:1,alignItems:'center',paddingVertical:10,borderRadius:radius.pill},
 row:{flexDirection:'row',alignItems:'center',gap:space.md,paddingVertical:space.md,paddingHorizontal:space.xs,borderBottomWidth:1,borderBottomColor:color.border},
 rowIcon:{width:44,height:44,borderRadius:radius.input,alignItems:'center',justifyContent:'center'},
 nav:{flexDirection:'row',borderTopWidth:1,borderTopColor:color.border,backgroundColor:color.bg,paddingTop:8,paddingBottom:12},
 navItem:{flex:1,alignItems:'center',gap:2,paddingVertical:4},
});
