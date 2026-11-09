import argparse,json,time
from .source import catalogue
from .service import Service

def main():
    parser=argparse.ArgumentParser(description='OPTIBELT raw-data simulated-live pipeline')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('list')
    sim=sub.add_parser('simulate');sim.add_argument('recording_id');sim.add_argument('--seconds',type=int,default=30)
    sim.add_argument('--speed',type=float,choices=[0.,1.,10.],default=1.);sim.add_argument('--output-root')
    args=parser.parse_args()
    if args.command=='list':
        print('\n'.join(r['recording_id'] for r in catalogue()));return
    service=Service(outputs=args.output_root)
    try:
        service.simulate(args.recording_id,args.seconds,args.speed);last=None
        while service.worker.is_alive():
            status=service.snapshot();p=status['pipeline'];key=(status['state'],p['score_count'] if p else None)
            if key!=last:
                print(json.dumps(dict(state=status['state'],pipeline_status=p['status'] if p else None,latest=p['latest'] if p else None)),flush=True);last=key
            time.sleep(.2)
        status=service.snapshot();print(json.dumps(status,indent=2))
        if status['error']:raise SystemExit(1)
    except KeyboardInterrupt:service.stop()
    finally:service.shutdown()
if __name__=='__main__':main()
