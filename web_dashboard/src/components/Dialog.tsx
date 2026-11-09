import {useEffect,useRef,type ReactNode} from 'react';
import {X} from '@phosphor-icons/react';
export function Dialog({open,title,onClose,children,modal=true}:{open:boolean;title:string;onClose:()=>void;children:ReactNode;modal?:boolean}){
 const ref=useRef<HTMLDialogElement>(null),close=useRef(onClose);close.current=onClose;
 useEffect(()=>{if(open&&!ref.current?.open){if(modal)ref.current?.showModal();else ref.current?.show()}if(!open&&ref.current?.open)ref.current.close()},[open,modal]);
 return <dialog ref={ref} className={`dialog ${modal?'':'alarm-notification'}`} aria-label={title} onCancel={e=>{e.preventDefault();close.current()}} onKeyDown={e=>{if(!modal&&e.key==='Escape'){e.preventDefault();close.current()}}}><header className="dialog-head"><h2>{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={18}/></button></header>{children}</dialog>;
}
