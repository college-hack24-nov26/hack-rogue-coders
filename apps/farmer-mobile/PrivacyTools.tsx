import React,{useState} from 'react';
import {View,Text} from 'react-native';
import {Api} from '../../packages/api-types';
import {space,type} from './theme';
import {Button,Field,Muted,Card} from './ui';
export function PrivacyTools({api}:{api:Api}){
 const [code,setCode]=useState('');const [reason,setReason]=useState('');const [result,setResult]=useState('');
 async function send(path:string,body:any){try{setResult(JSON.stringify(await api.request(path,'POST',body)))}catch(e){setResult((e as Error).message)}}
 return <View style={{marginVertical:space.md}}>
  <Text style={type.heading}>Account access & privacy</Text>
  <Field label="Staff invitation code" accessibilityLabel="Invitation code" value={code} onChange={setCode}/>
  <Button title="Redeem invitation" variant="secondary" icon="key-outline" onPress={()=>send('/access/redeem',{code})}/>
  <Muted>After redeeming, sign in to the assigned portal.</Muted>
  <Field label="Reason for data deletion request" accessibilityLabel="Deletion request reason" value={reason} onChange={setReason}/>
  <Button title="Request data deletion review" variant="secondary" icon="trash-outline" onPress={()=>send('/me/deletion-requests',{reason})}/>
  <Muted>Original complaint records and audit history require retention review. A request is not an immediate deletion.</Muted>
  {result?<Card tone="alt"><Text selectable style={type.small}>{result}</Text></Card>:null}
 </View>
}
