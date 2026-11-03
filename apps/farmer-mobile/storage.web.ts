export async function save(key:string,value:unknown){localStorage.setItem('jalsathi:'+key,JSON.stringify(value))}
export async function load(key:string){const v=localStorage.getItem('jalsathi:'+key);return v?JSON.parse(v):null}
export async function saveToken(value:string){}
export async function loadToken(){return ''}
