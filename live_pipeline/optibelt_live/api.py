from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated,Literal
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse,JSONResponse
from pydantic import BaseModel,ConfigDict,Field,StrictInt,StrictFloat,StrictBool
from .service import Service
from .source import catalogue
from .engine import Packet

class StrictModel(BaseModel):model_config=ConfigDict(extra='forbid')
class Condition(StrictModel):
    hp:Annotated[StrictFloat,Field(gt=0,allow_inf_nan=False)]
    load:StrictInt
    profile:Literal['invariant_speed','varying_speed']
    upper:StrictInt
class Simulation(StrictModel):
    recording_id:Annotated[str,Field(min_length=1,max_length=150)]
    seconds:Annotated[StrictInt,Field(ge=2,le=300)]=30
    speed:Literal[0.,1.,10.]=1.
class External(StrictModel):
    condition:Condition
    start_ns:Annotated[StrictInt,Field(ge=0)]
    source_id:Annotated[str,Field(min_length=1,max_length=150)]
    calibration_id:Annotated[str,Field(min_length=1,max_length=150)]
class Chunk(StrictModel):
    session_id:Annotated[str,Field(min_length=1,max_length=100)]
    sequence:Annotated[StrictInt,Field(ge=0)]
    start_ns:Annotated[StrictInt,Field(ge=0)]
    condition:Condition
    samples:dict[str,list[Annotated[StrictFloat,Field(allow_inf_nan=False)]]]
    rates:tuple[StrictInt,StrictInt,StrictInt,StrictInt,StrictInt]=(25600,25600,100000,100000,100000)
    motor_on:StrictBool|None=None

def create_app(service=None):
    manager=service or Service()
    @asynccontextmanager
    async def lifespan(app):
        yield
        manager.shutdown()
    app=FastAPI(title='OPTIBELT simulated-live pipeline',version='0.1.0',lifespan=lifespan)
    app.state.service=manager
    @app.middleware('http')
    async def local_requests(request,call_next):
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Cross-origin control requests are not accepted'},status_code=403)
        if int(request.headers.get('content-length','0'))>2_000_000:
            return JSONResponse({'detail':'Packet body exceeds 2 MB'},status_code=413)
        return await call_next(request)
    def call(fn,*args):
        try:return fn(*args)
        except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc
    @app.get('/api/health')
    def health():return {'application':'optibelt-live-pipeline','status':'ok','hardware_commands_enabled':False}
    @app.get('/api/catalog')
    def catalog():return [{k:v for k,v in r.items() if k not in ('path','sha256')} for r in catalogue(manager.project)]
    @app.get('/api/status')
    def status():return manager.snapshot()
    @app.post('/api/simulate')
    def simulate(r:Simulation):return call(manager.simulate,r.recording_id,r.seconds,r.speed)
    @app.post('/api/session')
    def session(r:External):return call(manager.open_external,r.condition.model_dump(),r.start_ns,r.source_id,r.calibration_id)
    @app.post('/api/packets')
    def packet(r:Chunk):return call(manager.ingest,Packet(r.session_id,r.sequence,r.start_ns,r.condition.model_dump(),r.samples,r.rates,r.motor_on))
    @app.post('/api/stop')
    def stop():return manager.stop()
    @app.post('/api/acknowledge')
    def acknowledge():return call(manager.acknowledge)
    @app.get('/')
    def index():return FileResponse(Path(__file__).with_name('monitor.html'))
    return app

app=create_app()
