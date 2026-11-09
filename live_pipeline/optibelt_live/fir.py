"""Bounded FIR prototype verified in streaming_experiment_001; live engine never flushes a fabricated tail."""
import numpy as np

class StreamingFIR:
 def __init__(self):
  k=np.arange(-1250,1251);self.h=np.sinc(k/125)/125*np.kaiser(2501,5.);self.h*=32/self.h.sum()
  self.buffer=np.empty(0);self.origin=0;self.count=0;self.next=0;self.first=[];self.last=None;self.closed=False;self.peak=0
 def push(self,x,final=False):
  x=np.asarray(x,dtype=float)
  if self.closed or x.ndim!=1 or not np.isfinite(x).all():raise ValueError('Invalid chunk or closed stream')
  if len(x):
   self.first=(self.first+x[:2].tolist())[:2] if len(self.first)<2 else self.first
   self.buffer=np.concatenate([self.buffer,x]);self.count+=len(x);self.last=float(x[-1]);self.peak=max(self.peak,len(self.buffer))
  if self.count<2:
   if final:raise ValueError('Need at least two samples')
   return np.empty(0)
  end=(self.count*32+124)//125 if final else max(0,(32*(self.count-1)-1250)//125+1)
  m=np.arange(self.next,end,dtype=np.int64);result=np.empty(len(m))
  for i in range(0,len(m),4096):
   t=m[i:i+4096]*125+1250;n=t[:,None]//32-np.arange(79)[None,:];hidx=t[:,None]-32*n;valid=(hidx>=0)&(hidx<2501)
   actual=n[(n>=0)&(n<self.count)&valid];assert len(actual)==0 or actual.min()>=self.origin
   vals=self.buffer[np.clip(n-self.origin,0,len(self.buffer)-1)]
   vals=np.where(n<0,self.first[0]+n*(self.first[1]-self.first[0]),vals)
   if final:vals=np.where(n>=self.count,self.last+(n-self.count+1)*(self.last-self.first[0])/(self.count-1),vals)
   result[i:i+len(t)]=np.sum(vals*self.h[np.clip(hidx,0,2500)]*valid,axis=1)
  self.next=end
  keep=max(0,(self.next*125-1250)//32);drop=min(len(self.buffer),max(0,keep-self.origin));self.buffer=self.buffer[drop:];self.origin+=drop
  self.closed=final
  return result
