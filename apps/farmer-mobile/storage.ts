import * as SQLite from 'expo-sqlite';
import * as SecureStore from 'expo-secure-store';
import {Platform} from 'react-native';
let db:SQLite.SQLiteDatabase;
async function database(){if(!db){db=await SQLite.openDatabaseAsync('jalsathi-cache.db');await db.execAsync('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)')}return db}
export async function save(key:string,value:unknown){if(Platform.OS==='web'){localStorage.setItem('jalsathi:'+key,JSON.stringify(value));return}await(await database()).runAsync('INSERT OR REPLACE INTO cache(key,value) VALUES (?,?)',key,JSON.stringify(value))}
export async function load(key:string){if(Platform.OS==='web'){const v=localStorage.getItem('jalsathi:'+key);return v?JSON.parse(v):null}const row=await(await database()).getFirstAsync<{value:string}>('SELECT value FROM cache WHERE key=?',key);return row?JSON.parse(row.value):null}
// Browser session credentials stay in memory. Native credentials use OS secure storage.
export async function saveToken(value:string){if(Platform.OS!=='web'){if(value)await SecureStore.setItemAsync('session',value);else await SecureStore.deleteItemAsync('session')}}
export async function loadToken(){return Platform.OS==='web'?'':(await SecureStore.getItemAsync('session'))||''}
