import React,{useState} from 'react';
import {View,Text,Pressable} from 'react-native';
import {color,radius,space,type} from './theme';
import {Icon,IconName} from './ui';

type Pt={x:number;y:number};
function Segments({pts,thick=2}:{pts:Pt[];thick?:number}){
 return <>{pts.slice(1).map((p,i)=>{const a=pts[i];const dx=p.x-a.x,dy=p.y-a.y;const len=Math.hypot(dx,dy);const ang=Math.atan2(dy,dx);
  return <View key={i} style={{position:'absolute',left:(a.x+p.x)/2-(len+1.5)/2,top:(a.y+p.y)/2-thick/2,width:len+1.5,height:thick,borderRadius:thick,backgroundColor:color.green,transform:[{rotate:ang+'rad'}]}}/>})}</>;
}
function scale(values:number[]){const min=Math.min(...values),max=Math.max(...values);const pad=(max-min)||1;return {lo:min-pad*.25,hi:max+pad*.25}}

/** Small trend line for a card. Larger values are drawn lower, matching "deeper groundwater". */
export function Sparkline({values,width=96,height=40}:{values:number[];width?:number;height?:number}){
 if(values.length<2)return null;
 const {lo,hi}=scale(values);
 const pts=values.map((v,i)=>({x:4+i/(values.length-1)*(width-8),y:4+((v-lo)/(hi-lo))*(height-8)}));
 return <View accessibilityElementsHidden importantForAccessibility="no" style={{width,height}}><Segments pts={pts}/><View style={{position:'absolute',left:pts[pts.length-1].x-3,top:pts[pts.length-1].y-3,width:6,height:6,borderRadius:3,backgroundColor:color.green}}/></View>;
}

/** Line chart with value axis and day labels. Larger depth is drawn lower. */
export function LineChart({values,labels,height=170,unit='m'}:{values:number[];labels:string[];height?:number;unit?:string}){
 const [w,setW]=useState(0);
 const {lo,hi}=scale(values);const padL=44,padR=10,padT=10,padB=6;const iw=Math.max(0,w-padL-padR),ih=height-padT-padB;
 const pts=values.map((v,i)=>({x:padL+(values.length>1?i/(values.length-1):.5)*iw,y:padT+((v-lo)/(hi-lo))*ih}));
 const ticks=[lo,(lo+hi)/2,hi];
 const every=Math.max(1,Math.ceil(labels.length/6));
 return <View accessibilityRole="image" accessibilityLabel={'Estimated depth by day, from '+values[0].toFixed(2)+' to '+values[values.length-1].toFixed(2)+' '+unit} onLayout={e=>setW(e.nativeEvent.layout.width)}>
  <View style={{height}}>
   {ticks.map((t,i)=>{const y=padT+((t-lo)/(hi-lo))*ih;return <View key={i} style={{position:'absolute',left:0,right:0,top:y}}><View style={{position:'absolute',left:padL,right:padR,height:1,backgroundColor:color.border}}/><Text style={[type.small,{position:'absolute',left:0,top:-8,width:padL-6,textAlign:'right',fontSize:11}]}>{t.toFixed(1)} {unit}</Text></View>})}
   {w>0&&<><Segments pts={pts}/>{pts.map((p,i)=><View key={i} style={{position:'absolute',left:p.x-4,top:p.y-4,width:8,height:8,borderRadius:4,backgroundColor:color.bg,borderWidth:2,borderColor:color.green}}/>)}</>}
  </View>
  <View style={{height:18,marginTop:4}}>{w>0&&labels.map((l,i)=>i%every===0||i===labels.length-1?<Text key={i} style={[type.small,{position:'absolute',left:pts[i].x-22,width:44,textAlign:'center',fontSize:11}]}>{l}</Text>:null)}</View>
 </View>;
}

/** Selectable report type card, as in the Submit Report mockup. */
export function RadioCard({icon,title,selected,onPress,tone='sage'}:{icon:IconName;title:string;selected:boolean;onPress:()=>void;tone?:'sage'|'water'|'warn'}){
 const tint={sage:color.green,water:color.water,warn:color.warn}[tone];const bg={sage:color.sage,water:color.waterBg,warn:color.warnBg}[tone];
 return <Pressable accessibilityRole="radio" accessibilityState={{selected}} accessibilityLabel={title} onPress={onPress} style={{flexDirection:'row',alignItems:'center',gap:space.md,padding:space.md,borderRadius:radius.card,borderWidth:selected?2:1,borderColor:selected?color.green:color.border,backgroundColor:selected?color.sage:color.bg,marginVertical:space.xs}}>
  <View style={{width:40,height:40,borderRadius:radius.input,backgroundColor:selected?color.bg:bg,alignItems:'center',justifyContent:'center'}}><Icon name={icon} size={22} tint={tint}/></View>
  <Text style={[type.heading,{flex:1}]}>{title}</Text>
  <View style={{width:24,height:24,borderRadius:12,borderWidth:2,borderColor:selected?color.green:color.border,alignItems:'center',justifyContent:'center',backgroundColor:selected?color.green:color.bg}}>{selected&&<View style={{width:8,height:8,borderRadius:4,backgroundColor:'#fff'}}/>}</View>
 </Pressable>;
}

/** Welcome illustration drawn with views: sun, rolling hills, a field path and trees. */
export function FarmScene({height=210}:{height?:number}){
 const tree=(left:number,bottom:number,s:number)=><View key={left} style={{position:'absolute',left,bottom,alignItems:'center'}}><View style={{width:s,height:s,borderRadius:s,backgroundColor:color.green}}/><View style={{width:s*.18,height:s*.4,backgroundColor:color.greenDark,marginTop:-2}}/></View>;
 return <View accessibilityElementsHidden importantForAccessibility="no" style={{height,overflow:'hidden',backgroundColor:color.waterBg,borderRadius:radius.card}}>
  <View style={{position:'absolute',right:34,top:24,width:46,height:46,borderRadius:23,backgroundColor:'#FFE6A3'}}/>
  <View style={{position:'absolute',left:24,top:34,width:70,height:22,borderRadius:22,backgroundColor:'#fff',opacity:.9}}/>
  <View style={{position:'absolute',left:-60,right:-60,bottom:-120,height:230,borderRadius:400,backgroundColor:'#BFE0C7'}}/>
  <View style={{position:'absolute',left:-20,width:'90%',bottom:-110,height:200,borderRadius:400,backgroundColor:'#8FCB9F'}}/>
  <View style={{position:'absolute',left:-80,right:-80,bottom:-150,height:210,borderRadius:400,backgroundColor:color.green}}/>
  <View style={{position:'absolute',left:'46%',bottom:-10,width:34,height:90,backgroundColor:'#E9D9A6',borderRadius:30,transform:[{rotate:'12deg'}]}}/>
  {tree(26,48,34)}{tree(70,34,24)}{tree(250,52,30)}{tree(292,38,22)}
 </View>;
}
