import React,{useEffect,useRef,useState} from 'react';
import {View,Text,TextInput,StyleSheet,Platform} from 'react-native';
import {Api,ApiError} from '../../packages/api-types';
import {color,radius,space,type,font} from './theme';
import {Button,Card,Logo,Notice} from './ui';

type Session={access_token:string;refresh_token?:string};
type Props={api:Api;onAuthenticated:(session:Session,created:boolean)=>void};
type Fields=Record<string,string>;
/** Ask the browser (Google Password Manager in Chrome) to offer saving these credentials. Nothing is stored by the app. */
async function offerToSave(id:string,password:string){
 try{const w:any=typeof window!=='undefined'?window:null;if(Platform.OS==='web'&&w?.PasswordCredential&&navigator.credentials)await navigator.credentials.store(new w.PasswordCredential({id,password,name:id}))}catch{}
}

export function AuthForm({api,onAuthenticated}:Props){
 const [mode,setMode]=useState<'signin'|'signup'>('signin');
 const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [confirmation,setConfirmation]=useState('');
 const [fields,setFields]=useState<Fields>({});const [message,setMessage]=useState('');const [busy,setBusy]=useState(false);const pending=useRef(false);
 const [capabilities,setCapabilities]=useState<{email_login:boolean;email_signup?:boolean}|null>(null);
 const signup=mode==='signup';

 useEffect(()=>{
  let active=true;setCapabilities(null);
  api.request('/auth/capabilities').then(result=>{if(active)setCapabilities(result)}).catch(()=>{});
  return ()=>{active=false};
 },[api.base]);

 function change(field:string,value:string,setter:(value:string)=>void){
  setter(value);setMessage('');setFields(previous=>{const next={...previous};delete next[field];return next});
 }
 function switchMode(){
  if(pending.current)return;
  setMode(signup?'signin':'signup');setPassword('');setConfirmation('');setFields({});setMessage('');
 }
 async function submit(){
  if(pending.current)return;
  const next:Fields={};const normalizedEmail=email.trim().toLowerCase();
  if(!normalizedEmail)next.email='Enter your email address.';
  else if(normalizedEmail.length>250||!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(normalizedEmail))next.email='Enter a valid email address.';
  if(!password.trim()||Array.from(password).length<10)next.password='Use a password with at least 10 characters.';
  else if(Array.from(password).length>200)next.password='Use a password with 200 characters or fewer.';
  if(signup&&!confirmation)next.confirmation='Confirm your password.';
  else if(signup&&confirmation!==password)next.confirmation='Passwords do not match.';
  setFields(next);setMessage('');
  if(Object.keys(next).length)return;
  pending.current=true;setBusy(true);
  try{
   const session=await api.request<Session>(signup?'/auth/register':'/auth/login','POST',{email:normalizedEmail,password});
   void offerToSave(normalizedEmail,password);
   setPassword('');setConfirmation('');onAuthenticated(session,signup);
  }catch(error){
   if(error instanceof ApiError&&Object.keys(error.fields).length)setFields(error.fields);
   else setMessage((error as Error).message||'Unable to continue. Please try again.');
  }finally{pending.current=false;setBusy(false)}
 }
 const unavailable=signup?capabilities?.email_signup===false:capabilities?.email_login===false;
 return <View>
  <View style={styles.hero}>
   <Logo size={84}/>
   <Text style={styles.wordmark}>JalSathi</Text>
   <Text style={styles.tagline}>Maharashtra · Water & Farming</Text>
  </View>
  <Card>
  <Text accessibilityRole="header" style={type.title}>{signup?'Create your farmer account':'Welcome to JalSathi'}</Text>
  <Text style={[type.small,{marginTop:space.xs,marginBottom:space.sm}]}>{signup?'Enter your email and choose a password to save your farms and track reports.':'Sign in to view your village, farms and reports.'}</Text>
  {message?<Notice tone="error">{message}</Notice>:null}
  {unavailable&&<Notice tone="error">{signup?'Account creation is not available on this server. Please contact the JalSathi administrator.':'Sign-in is not available on this server. Please contact the JalSathi administrator.'}</Notice>}
  <View style={styles.field}><Text style={styles.label}>Email</Text><TextInput accessibilityLabel="Email" accessibilityHint={fields.email} style={[styles.input,!!fields.email&&styles.invalid]} value={email} onChangeText={value=>change('email',value,setEmail)} autoCapitalize="none" autoCorrect={false} keyboardType="email-address" autoComplete="username" textContentType="username" importantForAutofill="yes" editable={!busy} placeholder="you@example.com" placeholderTextColor={color.textMuted}/>{fields.email&&<Text accessibilityRole="alert" style={styles.fieldError}>{fields.email}</Text>}</View>
  <View style={styles.field}><Text style={styles.label}>Password (10+ characters)</Text><TextInput accessibilityLabel="Password (10+ characters)" accessibilityHint={fields.password} style={[styles.input,!!fields.password&&styles.invalid]} value={password} onChangeText={value=>change('password',value,setPassword)} secureTextEntry autoCapitalize="none" autoCorrect={false} autoComplete={signup?'new-password':'current-password'} textContentType={signup?'newPassword':'password'} importantForAutofill="yes" editable={!busy} onSubmitEditing={signup?undefined:()=>void submit()}/>{fields.password&&<Text accessibilityRole="alert" style={styles.fieldError}>{fields.password}</Text>}</View>
  {signup&&<View style={styles.field}><Text style={styles.label}>Confirm password</Text><TextInput accessibilityLabel="Confirm password" accessibilityHint={fields.confirmation} style={[styles.input,!!fields.confirmation&&styles.invalid]} value={confirmation} onChangeText={value=>change('confirmation',value,setConfirmation)} secureTextEntry autoCapitalize="none" autoCorrect={false} autoComplete="new-password" textContentType="newPassword" importantForAutofill="yes" editable={!busy} onSubmitEditing={()=>void submit()}/>{fields.confirmation&&<Text accessibilityRole="alert" style={styles.fieldError}>{fields.confirmation}</Text>}</View>}
  <Button title={busy?(signup?'Creating account…':'Signing in…'):(signup?'Create account':'Sign in')} onPress={()=>void submit()} disabled={busy||unavailable}/>
  <Button title={signup?'Back to sign in':'Create farmer account'} variant="secondary" onPress={switchMode} disabled={busy}/>
  </Card>
 </View>;
}

const styles=StyleSheet.create({
 hero:{alignItems:'center',paddingVertical:space.xl,gap:space.xs},
 wordmark:{fontSize:34,fontWeight:'800',color:color.greenDark,fontFamily:font,letterSpacing:-.5,marginTop:space.sm},
 tagline:{fontSize:14,color:color.textMuted,fontFamily:font},
 field:{marginVertical:space.sm},label:{fontSize:13,fontWeight:'600',color:color.text,marginBottom:6,fontFamily:font},
 input:{borderWidth:1,borderColor:color.border,paddingVertical:13,paddingHorizontal:14,borderRadius:radius.input,fontSize:15,color:color.text,backgroundColor:color.bg,fontFamily:font},
 invalid:{borderColor:color.error},fieldError:{fontSize:13,color:color.error,lineHeight:20,marginTop:6,fontFamily:font},
});
