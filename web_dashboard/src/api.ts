export async function request<T>(url:string,init:RequestInit={}):Promise<T>{
 const response=await fetch(url,{...init,headers:{'Content-Type':'application/json',...init.headers}});
 const data=await response.json();
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'The requested data could not be loaded. Check the selected inputs.');
 return data as T;
}
export const recordingUrl=(id:string)=>`/api/recordings/${encodeURIComponent(id)}`;
export function csvDownload(name:string,rows:Record<string,unknown>[]){
 if(!rows.length)return;
 const headers=Object.keys(rows[0]);
 const cell=(v:unknown)=>`"${String(v??'').replaceAll('"','""')}"`;
 const csv=[headers.map(cell).join(','),...rows.map(row=>headers.map(key=>cell(row[key])).join(','))].join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
