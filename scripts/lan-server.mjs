// Phone-testing server for a trusted local network. Serves the three built apps from lan-dist
// and forwards API calls to the localhost-only API, allowing browser requests from these origins only.
// Usage: node scripts/lan-server.mjs 192.168.1.2     Stop it with the process id in lan-server.pid.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const ip=process.argv[2];
if(!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip||'')){console.error('Pass this computer\'s LAN IPv4 address.');process.exit(1)}
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..','lan-dist');
const apps=[{name:'farmer',port:8181},{name:'admin',port:5273},{name:'officials',port:5274}];
const apiPort=8100,upstream={host:'127.0.0.1',port:8000};
const origins=new Set(apps.map(a=>`http://${ip}:${a.port}`));
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.svg':'image/svg+xml','.ttf':'font/ttf','.ico':'image/x-icon','.map':'application/json'};

function serveStatic(dir){
 return http.createServer((req,res)=>{
  const url=new URL(req.url,'http://x');let file=path.join(dir,decodeURIComponent(url.pathname));
  if(!file.startsWith(dir)){res.writeHead(403).end();return}
  if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(dir,'index.html');
  res.writeHead(200,{'content-type':types[path.extname(file)]||'application/octet-stream','cache-control':'no-store'});
  fs.createReadStream(file).pipe(res);
 });
}
function cors(req,res){
 const o=req.headers.origin;if(o&&origins.has(o)){res.setHeader('access-control-allow-origin',o);res.setHeader('vary','Origin')}
}
const proxy=http.createServer((req,res)=>{
 cors(req,res);
 if(req.method==='OPTIONS'){
  res.writeHead(204,{'access-control-allow-methods':'GET,POST,PATCH,PUT,DELETE,OPTIONS','access-control-allow-headers':req.headers['access-control-request-headers']||'authorization,content-type,idempotency-key','access-control-max-age':'600'}).end();return;
 }
 const headers={...req.headers,host:`${upstream.host}:${upstream.port}`};delete headers.origin;delete headers.referer;
 const up=http.request({...upstream,path:req.url,method:req.method,headers},r=>{
  const h={...r.headers};delete h['access-control-allow-origin'];res.writeHead(r.statusCode,h);r.pipe(res);
 });
 up.on('error',()=>{if(!res.headersSent)res.writeHead(502,{'content-type':'application/json'});res.end('{"detail":"API unavailable"}')});
 req.pipe(up);
});
for(const a of apps)serveStatic(path.join(root,a.name)).listen(a.port,'0.0.0.0',()=>console.log(`${a.name}: http://${ip}:${a.port}`));
proxy.listen(apiPort,'0.0.0.0',()=>console.log(`api: http://${ip}:${apiPort}`));
fs.writeFileSync(path.join(root,'..','lan-server.pid'),String(process.pid));
